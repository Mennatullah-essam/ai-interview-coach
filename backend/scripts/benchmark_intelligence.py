"""Benchmark the evaluator and the question planner on fixed, hand-labelled cases.

Usage (from backend/):
    python scripts/benchmark_intelligence.py                       # current code
    python scripts/benchmark_intelligence.py --backend ../other    # another checkout (e.g. a baseline)
    python scripts/benchmark_intelligence.py --json out.json

It needs no database and no network. With SIMILARITY_BACKEND=sbert it also
measures the embedding model (load time, latency, memory). The cases in
tests/data/eval_cases.json are synthetic practice answers, so the numbers show
behaviour on those cases only; they are not a measure of real-world accuracy.
"""

import argparse
import json
import os
import resource
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CASES = HERE / "tests" / "data" / "eval_cases.json"
HOLDOUT = HERE / "tests" / "data" / "eval_cases_holdout.json"

ROLES = ["AI Engineer", "Machine Learning Engineer", "Data Scientist", "Software Engineer",
         "Backend Developer", "Frontend Developer", "Data Analyst"]


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def load(backend: Path):
    sys.path.insert(0, str(backend))
    os.chdir(backend)
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    os.environ.setdefault("JWT_SECRET", "benchmark-only-secret-0123456789abcdefghij")
    from app.core.config import get_settings
    from app.services.question_bank import load_bank_file

    entries, _ = load_bank_file(get_settings().question_bank_path)
    return entries


def evaluate_cases(entries, engine, cases_path: Path = CASES) -> dict:
    from app.scoring.scorer import evaluate_answer

    data = json.loads(cases_path.read_text(encoding="utf-8"))
    labels = data["labels"]
    rows, latencies = [], []
    for case in data["cases"]:
        entry = next(e for e in entries if e.text.startswith(case["q"]))
        kwargs = dict(question=entry.text, question_type=entry.question_type, answer=case["answer"],
                      reference=entry.reference_answer, key_points=entry.key_points)
        if "misconceptions" in evaluate_answer.__code__.co_varnames:
            kwargs["misconceptions"] = getattr(entry, "misconceptions", [])
        start = time.perf_counter()
        result = evaluate_answer(engine, **kwargs)
        latencies.append((time.perf_counter() - start) * 1000)
        dims = {d.key: d.score for d in getattr(result, "dimensions", [])}
        values = {
            "overall": result.overall_score,
            "relevance": dims.get("relevance", result.relevance),
            "correctness": dims.get("correctness", result.technical_depth),
            "specificity": dims.get("specificity", result.technical_depth),
        }
        expect = labels[case["label"]]
        failures = []
        for key, bound in expect.items():
            name, kind = key.rsplit("_", 1)
            value = values[name]
            if value is None:
                value = 0 if kind == "max" else 100  # "not assessed" (behavioral) satisfies both kinds
            if (kind == "min" and value < bound) or (kind == "max" and value > bound):
                failures.append(f"{name}={value} ({kind} {bound})")
        flagged = getattr(result, "unsupported_claims", None)
        rows.append({"q": case["q"], "label": case["label"], **values, "pass": not failures,
                     "failures": failures, "flagged_unsupported": bool(flagged) if flagged is not None else None})

    by_label = {}
    for row in rows:
        stats = by_label.setdefault(row["label"], {"n": 0, "pass": 0})
        stats["n"] += 1
        stats["pass"] += row["pass"]
    # Ordering: for every question, strong > partial > incorrect/irrelevant and paraphrase > keyword_stuffed.
    order_pairs = [("strong", "partial"), ("partial", "incorrect"), ("strong", "irrelevant"),
                   ("paraphrase", "keyword_stuffed"), ("concise_correct", "incorrect"), ("strong", "unsupported")]
    ordered = total = 0
    for q in {r["q"] for r in rows}:
        mine = {r["label"]: r["overall"] for r in rows if r["q"] == q}
        for hi, lo in order_pairs:
            if hi in mine and lo in mine:
                total += 1
                ordered += mine[hi] > mine[lo]
    unsupported = [r for r in rows if r["label"] == "unsupported"]
    return {
        "cases": len(rows),
        "agreement": round(sum(r["pass"] for r in rows) / len(rows), 3),
        "by_label": {k: f"{v['pass']}/{v['n']}" for k, v in sorted(by_label.items())},
        "pairwise_ordering": f"{ordered}/{total}",
        "unsupported_flagged": (f"{sum(bool(r['flagged_unsupported']) for r in unsupported)}/{len(unsupported)}"
                                if unsupported and unsupported[0]["flagged_unsupported"] is not None else "n/a"),
        "latency_ms_median": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 2),
        "failures": [{k: r[k] for k in ("q", "label", "overall", "correctness", "failures")} for r in rows if not r["pass"]],
    }


APPROPRIATE = {
    "strong": {"deepen", "continue"}, "paraphrase": {"deepen", "continue"},
    "concise_correct": {"continue", "deepen", "clarify"},
    "partial": {"probe_concept", "clarify", "request_example"}, "incorrect": {"probe_concept"},
    "irrelevant": {"request_example", "probe_concept", "clarify"},
    "keyword_stuffed": {"probe_concept", "clarify", "request_example"},
    "unsupported": {"request_example", "probe_concept"},
}


def agent_metrics(entries, engine) -> dict:
    """Follow-up decision for each labelled answer (first question of an adaptive interview),
    and how the agent behaves when a (simulated) LLM fails."""
    from app.models.enums import QuestionType
    from app.scoring.scorer import evaluate_answer

    data = json.loads(CASES.read_text(encoding="utf-8"))
    try:
        from app.intelligence import agent as agent_mod
    except ImportError:
        agent_mod = None
    appropriate = total = 0
    fallback_ok = fallback_total = 0
    actions: dict[str, dict[str, int]] = {}
    for case in data["cases"]:
        entry = next(e for e in entries if e.text.startswith(case["q"]))
        kwargs = dict(question=entry.text, question_type=entry.question_type, answer=case["answer"],
                      reference=entry.reference_answer, key_points=entry.key_points)
        if "misconceptions" in evaluate_answer.__code__.co_varnames:
            kwargs["misconceptions"] = getattr(entry, "misconceptions", [])
        r = evaluate_answer(engine, **kwargs)
        dims = {d.key: d.score for d in getattr(r, "dimensions", [])}
        if agent_mod is not None:
            ctx = agent_mod.AgentContext(
                question_text=entry.text, question_type=entry.question_type, category="core",
                key_points=entry.key_points, focus_skills=list(entry.skill_tags), target_role="AI Engineer",
                interview_type="technical", adaptive=True, reference=entry.reference_answer, overall=r.overall_score,
                dimensions=dims, demonstrated=r.demonstrated_concepts, missing=r.missing_concepts,
                incorrect_claims=r.incorrect_claims, unsupported_claims=r.unsupported_claims,
                evidence_level=r.evidence_level, answer_excerpt=case["answer"], follow_up_limit=2,
                questions_remaining=4, elapsed_minutes=2, time_budget_minutes=20)
            action = agent_mod.decide(ctx).action
            for failure in ("timeout", "schema_invalid", "off_topic"):
                fallback_total += 1
                try:
                    d = agent_mod.decide(ctx, _FailingGateway(failure))
                    fallback_ok += d.source == "rules" and agent_mod.validate(d, ctx) is None
                except Exception:
                    pass
        else:
            from app.intelligence import adaptive
            plan = adaptive.decide_follow_up(
                question_text=entry.text, question_type=entry.question_type, category="core",
                parent_reference=entry.reference_answer, focus_skills=list(entry.skill_tags), overall=r.overall_score,
                dimensions=getattr(r, "dimensions", None) and [d.as_dict() for d in r.dimensions],
                missing_concepts=getattr(r, "missing_concepts", []), used=0, limit=2, has_follow_up=False)
            action = {None: "continue", "clarify": "probe_concept", "example": "request_example",
                      "deeper": "deepen"}[plan.kind if plan else None]
        if entry.question_type is QuestionType.BEHAVIORAL and case["label"] == "incorrect":
            continue
        total += 1
        appropriate += action in APPROPRIATE[case["label"]]
        actions.setdefault(case["label"], {}).setdefault(action, 0)
        actions[case["label"]][action] += 1
    return {
        "appropriate_follow_up_rate": round(appropriate / total, 3),
        "actions_by_label": actions,
        "fallback_success_rate": round(fallback_ok / fallback_total, 3) if fallback_total else "n/a",
    }


class _FailingGateway:
    """Simulated LLM failures: timeout, schema-invalid output, or an off-topic proposal."""

    def __init__(self, mode):
        self.mode = mode

    def enabled_for(self, feature):
        return True

    def call(self, feature, system, user, schema, max_tokens=700):
        from app.llm.gateway import LLMCallResult

        if self.mode == "off_topic":
            value = schema.model_validate({"action": "clarify", "rationale": "x" * 5,
                                           "follow_up_question": "What is your favourite football team and why?"})
            return LLMCallResult(value, "ok")
        return LLMCallResult(None, self.mode)


def _tokens(text: str) -> set[str]:
    from app.scoring.text_utils import content_stems

    return set(content_stems(text))


def selection_metrics(entries, engine) -> dict:
    import inspect

    from app.intelligence.knowledge import role_requirements
    from app.intelligence.profile_extraction import build_profile
    from app.models import QuestionBankItem
    from app.models.enums import Difficulty, InterviewType
    from app.services.question_selection import match_roles, select_questions

    items = [QuestionBankItem(id=i, kind=e.kind, text=e.text, question_type=e.question_type, difficulty=e.difficulty,
                              role_tags=e.role_tags, skill_tags=e.skill_tags, ideal_answer=e.reference_answer,
                              key_points=e.key_points, is_active=True, misconceptions=getattr(e, "misconceptions", []))
             for i, e in enumerate(entries)]
    supports_history = "history" in inspect.signature(select_questions).parameters
    profile = build_profile("Skills\nPython, SQL, Docker, React, Git, PostgreSQL\nProjects\nShop API - FastAPI service with PostgreSQL.")

    on_role = total = dup = redundant_pairs = pairs = 0
    coverage, latencies, repeat_overlap = [], [], []
    deterministic = True
    for role in ROLES:
        req = role_requirements(match_roles(role))
        required = {s.lower() for s in req.required_skills} if req else set()
        for itype in (InterviewType.TECHNICAL, InterviewType.MIXED):
            for count in (5, 10, 15):
                kwargs = dict(target_role=role, interview_type=itype, difficulty=Difficulty.INTERMEDIATE,
                              question_count=count, cv_skills=["Python", "SQL", "Docker"], seed=f"{role}-{count}",
                              profile=profile, job_description=None, engine=engine)
                start = time.perf_counter()
                chosen = select_questions(items, **kwargs)
                latencies.append((time.perf_counter() - start) * 1000)
                if [q.text for q in select_questions(items, **kwargs)] != [q.text for q in chosen]:
                    deterministic = False
                texts = [q.text.lower() for q in chosen]
                dup += len(texts) - len(set(texts))
                roles_ok = match_roles(role)
                for q in chosen:
                    total += 1
                    bank = next((b for b in items if b.id == q.bank_question_id), None)
                    tags = set(bank.role_tags or []) if bank is not None else set()
                    on_role += (not tags) or "general" in tags or bool(tags & roles_ok) or q.category in ("cv_skill", "project", "follow_up")
                assessed = {t.lower() for q in chosen for t in (q.focus_skills or [])}
                assessed |= {t.lower() for q in chosen for b in items if b.id == q.bank_question_id for t in (b.skill_tags or [])}
                tech = [q for q in chosen if q.question_type.value == "technical"]
                if required and tech:
                    coverage.append(len(required & assessed) / min(len(required), len(tech)))
                toks = [_tokens(q.text + " " + " ".join(q.key_points or [])) for q in chosen]
                for i in range(len(toks)):
                    for j in range(i + 1, len(toks)):
                        pairs += 1
                        inter = len(toks[i] & toks[j]) / max(1, len(toks[i] | toks[j]))
                        redundant_pairs += inter >= 0.2
                if supports_history and count == 10:
                    second = select_questions(items, **(kwargs | {"seed": f"{role}-again",
                                                                   "history": [q.text for q in chosen]}))
                    repeat_overlap.append(len({q.text for q in second} & set(q.text for q in chosen)) / count)
                elif count == 10:
                    second = select_questions(items, **(kwargs | {"seed": f"{role}-again"}))
                    repeat_overlap.append(len({q.text for q in second} & set(q.text for q in chosen)) / count)
    return {
        "interviews": len(latencies),
        "on_role_rate": round(on_role / total, 3),
        "required_skill_coverage_mean": round(statistics.mean(coverage), 3),
        "duplicate_rate": round(dup / total, 4),
        "redundant_pair_rate": round(redundant_pairs / max(1, pairs), 4),
        "repeat_rate_next_interview": round(statistics.mean(repeat_overlap), 3),
        "deterministic": deterministic,
        "latency_ms_median": round(statistics.median(latencies), 2),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=str(HERE))
    parser.add_argument("--json")
    args = parser.parse_args()
    before = _rss_mb()
    start = time.perf_counter()
    entries = load(Path(args.backend).resolve())
    from app.scoring.similarity import get_engine

    engine = get_engine()
    load_ms = (time.perf_counter() - start) * 1000
    report = {
        "backend": args.backend,
        "engine": engine.name,
        "startup_ms": round(load_ms, 1),
        "memory_mb_after_load": round(_rss_mb(), 1),
        "memory_mb_delta": round(_rss_mb() - before, 1),
        "evaluation": evaluate_cases(entries, engine),
        "evaluation_holdout": evaluate_cases(entries, engine, HOLDOUT),
        "selection": selection_metrics(entries, engine),
        "agent": agent_metrics(entries, engine),
        "memory_mb_peak": round(_rss_mb(), 1),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
