"""Personalised improvement plan (Milestone 4, feature 5).

Evidence-based rules:
* Evidence per skill comes from questions that assess it (their focus skills),
  scored by the knowledge dimensions of the answer; behavioral competencies use
  the overall answer score; the six answer dimensions are tracked as well.
* GAP only with at least two weak answers (this interview plus earlier ones).
  One weak answer is "needs more evidence", never a gap.
* A required role skill with no evidence is "not yet demonstrated", which is
  not a claim that the candidate lacks it.
* Repeated patterns need at least two answers and 40 % of the interview.
* At most 5 prioritised next steps, 5 practice questions and 5 resources.
* Progress compares with the user's previous plan.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache

from app.intelligence.knowledge import data_path, skill_catalog

PLAN_VERSION = "plan-v2"
STRONG_FROM = 75
WEAK_BELOW = 55
GAP_MIN_EVIDENCE = 2
PATTERN_MIN_COUNT = 2
PATTERN_MIN_SHARE = 0.4
MAX_ITEMS = 5

DIMENSION_LABELS = {
    "relevance": "Relevance",
    "coverage": "Key concepts",
    "correctness": "Technical accuracy",
    "structure": "Structure",
    "specificity": "Evidence & examples",
    "communication": "Communication",
}
_PATTERN_MESSAGES = {
    "relevance": "answers drifted away from the question",
    "coverage": "answers missed key concepts",
    "correctness": "technical points were incomplete or inaccurate",
    "structure": "answers lacked a clear structure",
    "specificity": "answers stayed general without examples or numbers",
    "communication": "answers were too short or hard to follow",
}


@dataclass
class AnswerEvidence:
    interview_id: str
    question_text: str
    question_type: str  # technical | behavioral
    category: str | None
    focus_skills: list[str]
    overall: int
    dimensions: dict[str, int | None] = field(default_factory=dict)
    evidence_level: str = "sufficient"  # answers with "insufficient" evidence never count towards a gap
    group: str | None = None  # a question and its follow-up share a group and count as ONE piece of evidence

    @property
    def knowledge_score(self) -> int:
        values = [v for k, v in self.dimensions.items() if k in ("coverage", "correctness") and v is not None]
        return round(sum(values) / len(values)) if values else self.overall


@lru_cache
def _resources() -> dict:
    return json.loads(data_path("resources.json").read_text(encoding="utf-8"))


def _mean(values: list[int]) -> int:
    return int(sum(values) / len(values) + 0.5) if values else 0


def _counts_as_skill_evidence(answer: AnswerEvidence) -> bool:
    # Project questions are about the candidate's own project (their "focus" is the
    # project name), so they count for the answer dimensions but not as skill evidence.
    return not (answer.category == "project" or (answer.category == "follow_up" and not answer.focus_skills))


def _skill_evidence(answers: list[AnswerEvidence]) -> dict[str, list[int]]:
    """Scores per skill. A question and its follow-up are one piece of evidence (the better score),
    so a weak answer plus one probe on the same question never makes a "gap" on its own."""
    grouped: dict[tuple[str, str], int] = {}
    order: list[tuple[str, str]] = []
    for index, answer in enumerate(answers):
        if not _counts_as_skill_evidence(answer) or answer.evidence_level == "insufficient":
            continue  # too little content to judge: "not shown yet", never a weakness
        score = answer.overall if answer.question_type == "behavioral" else answer.knowledge_score
        group = answer.group or f"#{index}"
        for skill in answer.focus_skills:
            key = (skill, group)
            if key not in grouped:
                order.append(key)
                grouped[key] = score
            else:
                grouped[key] = max(grouped[key], score)
    evidence: dict[str, list[int]] = defaultdict(list)
    for skill, group in order:
        evidence[skill].append(grouped[(skill, group)])
    return evidence


def _skill_examples(answers: list[AnswerEvidence]) -> dict[str, list[dict]]:
    examples: dict[str, list[dict]] = defaultdict(list)
    for answer in answers:
        if not _counts_as_skill_evidence(answer) or answer.evidence_level == "insufficient":
            continue
        score = answer.overall if answer.question_type == "behavioral" else answer.knowledge_score
        for skill in answer.focus_skills:
            examples[skill].append({"question": answer.question_text, "score": score, "interview_id": answer.interview_id})
    return examples


def _dimension_evidence(answers: list[AnswerEvidence]) -> dict[str, list[int]]:
    evidence: dict[str, list[int]] = defaultdict(list)
    for answer in answers:
        for key, value in answer.dimensions.items():
            if value is not None:
                evidence[key].append(value)
    return evidence


def classify(scores_now: list[int], scores_before: list[int]) -> str:
    combined = scores_now + scores_before
    average = _mean(combined)
    if average >= STRONG_FROM:
        return "strong"
    if average < WEAK_BELOW:
        weak_count = sum(1 for s in combined if s < WEAK_BELOW)
        return "gap" if weak_count >= GAP_MIN_EVIDENCE else "needs_evidence"
    return "developing"


def build_plan(
    *,
    interview_id: str,
    target_role: str,
    required_skills: list[str],
    job_skills: list[str],
    profile_skills: list[str],
    current: list[AnswerEvidence],
    history: list[AnswerEvidence],
    previous_plan: dict | None,
    previous_overall: int | None,
    current_overall: int,
    practice_pool: list[dict],
) -> dict:
    """Return the plan as a JSON-serialisable dict. Deterministic for the same inputs."""
    now_skills = _skill_evidence(current)
    before_skills = _skill_evidence(history)
    now_dims = _dimension_evidence(current)
    examples = _skill_examples([*history, *current])

    strengths, weaknesses = [], []
    for skill in sorted(now_skills, key=lambda s: (-len(now_skills[s]), s)):
        status = classify(now_skills[skill], before_skills.get(skill, []))
        count = len(now_skills[skill]) + len(before_skills.get(skill, []))
        score = _mean(now_skills[skill] + before_skills.get(skill, []))
        interviews = {e["interview_id"] for e in examples.get(skill, [])}
        entry = {"name": skill, "kind": "skill", "score": score, "evidence_count": count,
                 "interviews": len(interviews),
                 "examples": [{"question": e["question"], "score": e["score"]} for e in examples.get(skill, [])[-2:]]}
        if status == "strong":
            consistent = len(interviews) >= 2
            strengths.append(entry | {"consistent": consistent, "evidence": (
                f"Strong across {len(interviews)} interviews (average {score}/100)." if consistent
                else f"Average {score}/100 over {count} answer(s).")})
        elif status in ("gap", "needs_evidence"):
            label = ("Weak in at least two answers" if status == "gap"
                     else "Only one weak answer so far; practise more before drawing conclusions")
            weaknesses.append(entry | {"status": status, "evidence": f"{label} (average {score}/100)."})
    for key, values in now_dims.items():
        score = _mean(values)
        if score >= STRONG_FROM and len(values) >= 2:
            strengths.append({"name": DIMENSION_LABELS[key], "kind": "dimension", "score": score,
                              "evidence_count": len(values), "evidence": f"Average {score}/100 across {len(values)} answers."})

    patterns = []
    total = len(current)
    for key, values in now_dims.items():
        low = sum(1 for v in values if v < WEAK_BELOW)
        if low >= PATTERN_MIN_COUNT and low / max(1, len(values)) >= PATTERN_MIN_SHARE:
            patterns.append({"dimension": key, "label": DIMENSION_LABELS[key], "count": low, "total": len(values),
                             "message": f"In {low} of {len(values)} answers, {_PATTERN_MESSAGES[key]}."})
    patterns.sort(key=lambda p: (-p["count"] / p["total"], p["dimension"]))

    have = {s.lower() for s in profile_skills}
    weak_names = {w["name"].lower(): w for w in weaknesses}
    strong_names = {s["name"].lower() for s in strengths}
    role_items = []
    for skill in required_skills:
        source = "job description" if skill in job_skills else target_role
        lower = skill.lower()
        if lower in weak_names:
            status = "weak" if weak_names[lower]["status"] == "gap" else "needs_evidence"
        elif lower in strong_names:
            continue
        elif lower not in have and lower not in {s.lower() for s in now_skills}:
            status = "not_demonstrated"
        else:
            continue
        role_items.append({"skill": skill, "status": status, "required_by": source})

    # --- prioritised next steps --------------------------------------------------------
    required_lower = {s.lower() for s in required_skills}
    candidates = []
    for w in weaknesses:
        if w["status"] == "gap":
            priority = 100 if w["name"].lower() in required_lower else 70
            candidates.append((priority, {
                "title": f"Strengthen {w['name']}",
                "detail": f"Review the core concepts of {w['name']} and answer two practice questions on it.",
                "evidence": w["evidence"],
            }))
    for p in patterns:
        candidates.append((80, {
            "title": f"Improve {p['label'].lower()}",
            "detail": _resources()["dimensions"].get(p["dimension"], "Practise this dimension deliberately."),
            "evidence": p["message"],
        }))
    for item in role_items:
        if item["status"] == "not_demonstrated":
            candidates.append((60, {
                "title": f"Show evidence of {item['skill']}",
                "detail": f"{item['skill']} is expected for {item['required_by']}. If you have used it, add it to your "
                          f"profile and prepare an example; if not, start with the resource below.",
                "evidence": "Not yet demonstrated in your profile or answers.",
            }))
    for w in weaknesses:
        if w["status"] == "needs_evidence":
            candidates.append((40, {
                "title": f"Practise {w['name']} again",
                "detail": "One weaker answer is not enough to call it a gap. Try another question on it.",
                "evidence": w["evidence"],
            }))
    candidates.sort(key=lambda c: -c[0])
    next_steps = []
    for priority, step in candidates[:MAX_ITEMS]:
        level = "high" if priority >= 80 else "medium" if priority >= 60 else "low"
        next_steps.append(step | {"priority": level})

    # --- practice questions and resources ------------------------------------------------
    focus = [w["name"] for w in weaknesses] + [i["skill"] for i in role_items]
    focus_lower = [f.lower() for f in focus]
    weak_behavioral = any(p["dimension"] in ("structure", "specificity", "communication") for p in patterns)
    practice = []
    for question in practice_pool:
        tags = [t.lower() for t in question.get("skill_tags", [])]
        hit = next((f for f in focus_lower if f in tags), None)
        if hit:
            skill = focus[focus_lower.index(hit)]
            practice.append(question | {"reason": f"Practises {skill}."})
        elif weak_behavioral and question["type"] == "behavioral" and len(practice) < MAX_ITEMS:
            practice.append(question | {"reason": "Practises structure and concrete examples (STAR)."})
        if len(practice) >= MAX_ITEMS:
            break

    resources, seen_titles = [], set()
    library = _resources()
    catalog = skill_catalog()
    for skill in focus:
        item = library["skills"].get(skill)
        if item and item["title"] not in seen_titles:
            resources.append({"skill": skill, "title": item["title"], "url": item["url"], "kind": "documentation"})
            seen_titles.add(item["title"])
        elif not item:
            category = catalog.category_of.get(skill)
            if category and category not in seen_titles:
                resources.append({"skill": skill, "title": library["categories"][category], "url": None, "kind": "practice"})
                seen_titles.add(category)
        if len(resources) >= MAX_ITEMS:
            break
    for p in patterns:
        if len(resources) >= MAX_ITEMS:
            break
        resources.append({"skill": p["label"], "title": library["dimensions"][p["dimension"]], "url": None, "kind": "practice"})

    # --- progress -------------------------------------------------------------------------
    progress_items = []
    if previous_plan:
        before = {s["name"]: s["score"] for s in previous_plan.get("scores", [])}
        for name, score in ((s["name"], s["score"]) for s in _scores(now_skills, now_dims)):
            if name in before:
                progress_items.append({"name": name, "previous": before[name], "current": score,
                                       "change": score - before[name]})
    progress = {
        "previous_interview_id": previous_plan.get("interview_id") if previous_plan else None,
        "overall": None if previous_overall is None else {
            "previous": previous_overall, "current": current_overall, "change": current_overall - previous_overall},
        "items": progress_items[:8],
    }

    # --- evidence that was too thin to judge ---------------------------------------------------------
    judged = set(now_skills) | set(before_skills)
    thin = sorted({s for a in current if a.evidence_level == "insufficient" and _counts_as_skill_evidence(a)
                   for s in a.focus_skills} - judged)
    insufficient = [{"name": s, "evidence": "Your answer was too brief to judge this skill; it is not counted as a weakness."}
                    for s in thin][:MAX_ITEMS]

    # --- competency overview: CV/profile versus interview evidence ------------------------------------
    have_lower = {s.lower(): s for s in profile_skills}
    overview = []
    for skill in list(dict.fromkeys([*required_skills, *sorted(now_skills)])):
        scores = now_skills.get(skill, []) + before_skills.get(skill, [])
        status = classify(now_skills.get(skill, []), before_skills.get(skill, [])) if scores else "unassessed"
        overview.append({
            "name": skill,
            "required": skill in required_skills,
            "in_profile": skill.lower() in have_lower,
            "interview_status": {"strong": "demonstrated", "gap": "weak"}.get(status, status),
            "average": _mean(scores) if scores else None,
            "answers": len(scores),
        })

    # --- exercises (from the curated catalogue only) ---------------------------------------------------
    library_ = _resources()
    exercises = []
    for p in patterns:
        tip = library_["dimensions"].get(p["dimension"])
        if tip:
            exercises.append({"title": tip, "reason": p["message"]})
    for w in weaknesses:
        category = skill_catalog().category_of.get(w["name"])
        tip = library_["categories"].get(category) if category else None
        if tip and all(e["title"] != tip for e in exercises):
            exercises.append({"title": tip, "reason": f"For {w['name']}: {w['evidence']}"})
    exercises = exercises[:MAX_ITEMS]

    gap_count = sum(1 for w in weaknesses if w["status"] == "gap")
    summary = (f"Based on {total} answer(s) for {target_role}: {len(strengths)} strength(s), "
               f"{gap_count} skill gap(s) confirmed by more than one answer, and {len(patterns)} repeated pattern(s).")
    return {
        "version": PLAN_VERSION,
        "interview_id": interview_id,
        "target_role": target_role,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_score": current_overall,
        "summary": summary,
        "strengths": strengths[:MAX_ITEMS],
        "weaknesses": weaknesses[:MAX_ITEMS],
        "role_skills_to_practice": role_items[:MAX_ITEMS],
        "patterns": patterns[:3],
        "practice_questions": practice[:MAX_ITEMS],
        "resources": resources[:MAX_ITEMS],
        "next_steps": next_steps,
        "exercises": exercises,
        "competencies": overview[:12],
        "insufficient_evidence": insufficient,
        "progress": progress,
        "scores": _scores(now_skills, now_dims),
        "notes": [
            "A skill is only called a gap after at least two weak answers; a single weak answer is marked "
            "'needs more evidence'.",
            "'Not yet demonstrated' means the skill is not in your profile and was not assessed, not that you lack it.",
            "Very brief answers are treated as 'not enough evidence' and never count as a weakness.",
            "Interview results never change the skills you confirmed in your profile.",
            "Scores are automated estimates for practice.",
        ],
    }


def _scores(skills: dict[str, list[int]], dims: dict[str, list[int]]) -> list[dict]:
    items = [{"name": s, "score": _mean(v)} for s, v in sorted(skills.items())]
    items += [{"name": DIMENSION_LABELS[k], "score": _mean(v)} for k, v in sorted(dims.items())]
    return items
