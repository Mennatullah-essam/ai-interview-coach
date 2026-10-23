"""Milestone 5: semantic retrieval, the hybrid interview agent, evidence-based
evaluation, the optional LLM layer and evidence-based coaching.

No test needs network access or real LLM credentials: provider behaviour is
simulated with deterministic fakes.
"""

import io
import json
import urllib.error
from pathlib import Path

import pytest

from app.intelligence import agent as agent_mod
from app.intelligence.agent import AgentContext, AgentProposal, budget_reason, decide, propose_rules, validate
from app.intelligence.competencies import build_ledger, competency_model
from app.intelligence.evaluation_review import EvaluationReview, apply_review
from app.intelligence.improvement import AnswerEvidence, build_plan
from app.intelligence.profile_extraction import build_profile
from app.intelligence.retrieval import SemanticIndex, question_document, reset_indexes_for_tests
from app.llm.gateway import LLMGateway, build_gateway, is_local_url, minimise, set_llm_for_tests
from app.llm.providers import LLMError, LLMResponse, OpenAICompatibleProvider, parse_json_object
from app.models import QuestionBankItem
from app.models.enums import Difficulty, InterviewType, QuestionKind, QuestionType
from app.scoring.scorer import evaluate_answer
from app.scoring.similarity import LexicalSimilarity
from app.services.question_selection import select_questions
from tests.helpers import answer_and_evaluate, create_interview, upload_cv
from tests.test_scoring_and_selection import _bank_items, bank_entries  # noqa: F401  (fixture)

ENGINE = LexicalSimilarity()
DATA = Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def _no_llm():
    """Every test starts with the LLM disabled (the default) and fresh retrieval indexes."""
    set_llm_for_tests(LLMGateway(None, status="disabled", features={"agent", "evaluation"}))
    reset_indexes_for_tests()
    yield
    set_llm_for_tests(None)
    reset_indexes_for_tests()


def _items(bank_entries):  # noqa: F811
    items = _bank_items(bank_entries)
    for item, entry in zip(items, bank_entries, strict=True):
        item.misconceptions = list(entry.misconceptions)
    return items


def _plan(bank_entries, **overrides):  # noqa: F811
    kwargs = dict(target_role="Backend Developer", interview_type=InterviewType.TECHNICAL,
                  difficulty=Difficulty.INTERMEDIATE, question_count=10, cv_skills=["Python"], seed="seed-1",
                  engine=ENGINE) | overrides
    return select_questions(_items(bank_entries), **kwargs)


# =================================================================================================
# Retrieval
# =================================================================================================


def test_semantic_index_matches_synonyms_and_aliases():
    index = SemanticIndex(None)
    k8s = question_document("How do you roll out containers?", ["pods and deployments"], ["Kubernetes"])
    assert index.similarity("experience with k8s clusters", k8s) > index.similarity("experience with k8s clusters",
                                                                                     "How do you bake bread?")
    reg = "Regularization techniques for neural networks"
    assert index.similarity("I use weight decay and dropout", reg) > 0
    assert index.similarity("I use weight decay and dropout", "How do you bake bread?") == 0


def test_competency_model_shares_ids_across_skills_and_behaviors():
    model = competency_model()
    assert model.id_for("k8s") == "skill:Kubernetes"
    assert model.id_for("Teamwork", "behavior") == "behavior:Teamwork"
    assert "Docker" in model.related("Kubernetes")
    assert model.description("SQL")


def test_selection_covers_several_required_skills_and_explains_it(bank_entries):  # noqa: F811
    from app.intelligence.knowledge import role_requirements
    from app.services.question_selection import match_roles

    chosen = _plan(bank_entries)
    required = {s.lower() for s in role_requirements(match_roles("Backend Developer")).required_skills}
    covered = {s.lower() for q in chosen for s in q.focus_skills} & required
    assert len(covered) >= 4
    coverage = [q for q in chosen if q.category == "coverage"]
    assert coverage and all(q.reason.startswith("Covers ") for q in coverage)


def test_no_duplicate_or_near_duplicate_questions(bank_entries):  # noqa: F811
    items = _items(bank_entries)
    original = next(i for i in items if i.text.startswith("How do database indexes work"))
    clone = QuestionBankItem(id=999, kind=QuestionKind.GENERIC, text=original.text.replace("How do", "How exactly do"),
                             question_type=original.question_type, difficulty=original.difficulty,
                             role_tags=original.role_tags, skill_tags=original.skill_tags,
                             ideal_answer=original.ideal_answer, key_points=original.key_points, is_active=True,
                             misconceptions=[])
    chosen = select_questions([*items, clone], target_role="Backend Developer", interview_type=InterviewType.TECHNICAL,
                              difficulty=Difficulty.INTERMEDIATE, question_count=15, cv_skills=[], seed="dup",
                              engine=ENGINE)
    texts = [q.text for q in chosen]
    assert len(texts) == len(set(texts))
    assert not ({original.text, clone.text} <= set(texts))  # the near-duplicate is never asked alongside the original


def test_history_reduces_repeats_in_the_next_interview(bank_entries):  # noqa: F811
    first = _plan(bank_entries, seed="a")
    again_without = _plan(bank_entries, seed="b")
    again_with = _plan(bank_entries, seed="b", history=[q.text for q in first])
    overlap = lambda xs: len({q.text for q in xs} & {q.text for q in first})  # noqa: E731
    assert overlap(again_with) < overlap(again_without)
    assert overlap(again_with) <= 3


def test_weak_competency_is_prioritised_with_an_evidence_note(bank_entries):  # noqa: F811
    weak_sql = [AnswerEvidence(interview_id=f"i{n}", question_text="q", question_type="technical", category="core",
                               focus_skills=["SQL"], overall=30, dimensions={"coverage": 25, "correctness": 30})
                for n in range(2)]
    ledger = build_ledger(None, weak_sql)
    assert ledger.status("SQL") == "weak"
    chosen = _plan(bank_entries, question_count=5, ledger=ledger)
    sql = [q for q in chosen if "SQL" in q.focus_skills]
    assert any(q.category == "coverage" and "averaged" in q.reason for q in sql)


def test_ranking_is_stable_and_works_without_embeddings(bank_entries, monkeypatch):  # noqa: F811
    from app.scoring import similarity

    def unavailable():
        raise similarity.EngineUnavailable("no model")
    monkeypatch.setattr(similarity, "get_engine", unavailable)
    first = [(q.text, q.reason) for q in _plan(bank_entries, engine=None)]
    assert first == [(q.text, q.reason) for q in _plan(bank_entries, engine=None)]


class FakeEncoder:
    """Deterministic stand-in for a Sentence-Transformers model (bag of hashed words, normalised)."""

    def __init__(self):
        self.calls = 0

    def encode(self, texts, normalize_embeddings=True):
        import math
        self.calls += 1
        out = []
        for text in texts:
            vec = [0.0] * 32
            for word in text.lower().split():
                vec[sum(map(ord, word)) % 32] += 1
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def test_embedding_index_caches_vectors_in_memory_and_on_disk(tmp_path):
    from app.scoring.similarity import SbertSimilarity

    encoder = FakeEncoder()
    engine = SbertSimilarity("fake/model", encoder=encoder)
    index = SemanticIndex(engine, cache_dir=tmp_path)
    docs = ["How do database indexes work?", "Explain overfitting."]
    index.warm(docs)
    calls = encoder.calls
    assert index.similarity(docs[0], docs[0]) == pytest.approx(1.0, abs=1e-4)
    index.similarity(docs[0], docs[1])
    assert encoder.calls == calls  # nothing re-encoded
    assert (tmp_path / "fake_model.json").exists()
    reloaded = SemanticIndex(SbertSimilarity("fake/model", encoder=FakeEncoder()), cache_dir=tmp_path)
    assert reloaded.vectors(docs) == index.vectors(docs)


def test_selection_uses_embeddings_when_loaded(bank_entries):  # noqa: F811
    from app.scoring.similarity import SbertSimilarity

    engine = SbertSimilarity("fake/model", encoder=FakeEncoder())
    chosen = _plan(bank_entries, engine=engine)
    assert len(chosen) == 10 and len({q.text for q in chosen}) == 10


# =================================================================================================
# Interview agent
# =================================================================================================


def _ctx(**overrides) -> AgentContext:
    base = dict(question_text="What is overfitting, and how do you detect and prevent it?",
                question_type=QuestionType.TECHNICAL, category="core",
                key_points=["training versus validation gap", "cross-validation", "regularization", "early stopping"],
                focus_skills=["Machine Learning"], target_role="AI Engineer", interview_type="technical",
                adaptive=True, reference="ref", overall=40, dimensions={"specificity": 30},
                demonstrated=["training versus validation gap"], missing=["cross-validation", "regularization"],
                incorrect_claims=[], unsupported_claims=[], evidence_level="sufficient",
                answer_excerpt="An answer.", follow_ups_used=0, follow_up_limit=2, questions_remaining=4,
                elapsed_minutes=3, time_budget_minutes=20)
    return AgentContext(**(base | overrides))


def test_weak_answer_probes_the_first_missing_concept():
    d = decide(_ctx())
    assert d.action == "probe_concept" and d.target_concept == "cross-validation" and d.source == "rules"
    assert "cross-validation" in d.follow_up_question and d.key_points[0] == "cross-validation"


def test_agent_uses_interview_context_to_avoid_repeat_probes():
    assert decide(_ctx(probed_concepts={"cross-validation"})).target_concept == "regularization"
    shown_earlier = decide(_ctx(demonstrated_in_session={"cross-validation"}))
    assert shown_earlier.target_concept == "regularization"
    everything_probed = decide(_ctx(probed_concepts={"cross-validation", "regularization"}))
    assert everything_probed.action == "request_example"


def test_incorrect_claim_is_probed_and_quoted_as_evidence():
    d = decide(_ctx(overall=60, incorrect_claims=[{"explanation": "That describes underfitting.",
                                                     "evidence": "Overfitting means the model is too simple."}]))
    assert d.action == "probe_concept"
    assert any("too simple" in e for e in d.evidence)


def test_unsupported_claim_requests_evidence():
    d = decide(_ctx(overall=60, missing=[], unsupported_claims=["XGBoost always handles it perfectly."]))
    assert d.action == "request_example" and "XGBoost always" in d.follow_up_question


def test_strong_answer_is_deepened_once_per_competency():
    assert decide(_ctx(overall=88, missing=[])).action == "deepen"
    assert decide(_ctx(overall=88, missing=[], deepened_competencies={"Machine Learning"})).action == "continue"


def test_adequate_answer_continues():
    assert decide(_ctx(overall=68, missing=[], dimensions={"specificity": 70})).action == "continue"


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"adaptive": False}, "adaptive_off"),
    ({"is_follow_up": True}, "no_follow_up_on_follow_up"),
    ({"has_follow_up": True}, "already_followed_up"),
    ({"follow_ups_used": 2}, "follow_up_budget_used"),
    ({"elapsed_minutes": 25}, "time_budget_used"),
])
def test_limits_stop_follow_ups(overrides, reason):
    d = decide(_ctx(**overrides))
    assert d.action == "continue" and d.policy == reason and budget_reason(_ctx(**overrides)) == reason


def test_competency_cannot_be_probed_endlessly():
    d = decide(_ctx(follow_ups_per_competency={"Machine Learning": 2}))
    assert d.action == "continue" and d.policy == "competency_probed_enough"


class FakeGateway:
    """Simulates the LLM gateway: returns a fixed proposal or failure reason."""

    def __init__(self, data=None, reason="ok"):
        self.data, self.reason, self.calls = data, reason, 0

    def enabled_for(self, feature):
        return True

    def call(self, feature, system, user, schema, max_tokens=700):
        from app.llm.gateway import LLMCallResult

        self.calls += 1
        self.last_prompt = user
        if self.data is None:
            return LLMCallResult(None, self.reason)
        try:
            return LLMCallResult(schema.model_validate(self.data), "ok", "fake-model", 5)
        except Exception:
            return LLMCallResult(None, "schema_invalid")


def test_valid_llm_proposal_is_used():
    gw = FakeGateway({"action": "probe_concept", "rationale": "Regularisation was not explained.",
                      "evidence": ["missing regularization"], "target_concept": "Regularization",
                      "follow_up_question": "How would regularization help prevent overfitting in this model?"})
    d = decide(_ctx(answer_excerpt="Call me on +20 100 123 4567 or a@b.com"), gw)
    assert d.source == "llm" and d.target_concept == "regularization" and d.llm_status == "ok"
    assert "a@b.com" not in gw.last_prompt and "123 4567" not in gw.last_prompt  # contact details removed


@pytest.mark.parametrize(("data", "status"), [
    ({"action": "probe_concept", "rationale": "ok ok", "target_concept": "quantum entanglement",
      "follow_up_question": "Can you explain quantum entanglement in this model?"}, "rejected:concept_not_in_rubric"),
    ({"action": "clarify", "rationale": "ok ok", "follow_up_question": "What is your favourite football team, honestly?"},
     "rejected:off_topic"),
    ({"action": "clarify", "rationale": "ok ok", "follow_up_question": "How old are you and is overfitting a problem for you?"},
     "rejected:asks_personal_data"),
    ({"action": "deepen", "rationale": "ok ok", "follow_up_question": "short?"}, "rejected:invalid_question_text"),
    ({"action": "fly_away", "rationale": "x"}, "schema_invalid"),
])
def test_invalid_llm_proposals_fall_back_to_rules(data, status):
    d = decide(_ctx(), FakeGateway(data))
    assert d.source == "rules" and d.action == "probe_concept" and d.llm_status == status


@pytest.mark.parametrize("reason", ["timeout", "rate_limited", "connection", "circuit_open"])
def test_llm_outage_falls_back_to_rules(reason):
    d = decide(_ctx(), FakeGateway(None, reason))
    assert d.source == "rules" and d.action == "probe_concept" and d.llm_status == reason


def test_llm_is_not_called_when_no_follow_up_is_allowed():
    gw = FakeGateway({"action": "continue", "rationale": "fine"})
    decide(_ctx(follow_ups_used=2), gw)
    assert gw.calls == 0


def test_llm_continue_is_respected():
    d = decide(_ctx(), FakeGateway({"action": "continue", "rationale": "Enough evidence already."}))
    assert d.action == "continue" and d.source == "llm"


# =================================================================================================
# LLM gateway and provider
# =================================================================================================


def test_llm_is_disabled_by_default(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert build_gateway().status == "disabled"


def test_external_llm_needs_explicit_permission(monkeypatch):
    from app.core.config import get_settings

    for allow, expected in (("false", "blocked_external"), ("true", "active")):
        monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("LLM_MODEL", "some-model")
        monkeypatch.setenv("LLM_ALLOW_EXTERNAL", allow)
        get_settings.cache_clear()
        gateway = build_gateway()
        assert gateway.status == expected
        assert "example.com" not in json.dumps(gateway.describe())  # no URLs or keys in status output
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_ALLOW_EXTERNAL", "false")
    get_settings.cache_clear()
    assert build_gateway().status == "active"  # a local server (e.g. Ollama) keeps data on the machine
    get_settings.cache_clear()


def test_local_url_detection_and_minimisation():
    assert is_local_url("http://localhost:11434/v1") and is_local_url("http://127.0.0.1:8080")
    assert not is_local_url("https://api.openai.com/v1")
    cleaned = minimise("Mail me at jane.doe@mail.com, call +20 100 123 4567, see https://x.io/me")
    assert "jane" not in cleaned and "4567" not in cleaned and "x.io" not in cleaned


def test_circuit_breaker_opens_after_repeated_failures():
    class Broken:
        name, model = "fake", "m"

        def complete_json(self, system, user, max_tokens=700):
            raise LLMError("timeout")
    gw = LLMGateway(Broken(), status="active", features={"agent"}, failure_threshold=2, cooldown_seconds=60)
    assert gw.call("agent", "s", "u", AgentProposal).reason == "timeout"
    assert gw.call("agent", "s", "u", AgentProposal).reason == "timeout"
    assert gw.call("agent", "s", "u", AgentProposal).reason == "circuit_open"
    assert gw.call("evaluation", "s", "u", AgentProposal).reason == "feature_off"


def test_gateway_validates_schema():
    class Talker:
        name, model = "fake", "m"

        def complete_json(self, system, user, max_tokens=700):
            return LLMResponse({"action": "probe_concept"}, "m", 3)  # missing rationale
    gw = LLMGateway(Talker(), status="active", features={"agent"})
    assert gw.call("agent", "s", "u", AgentProposal).reason == "schema_invalid"


def _reply(content: str) -> io.BytesIO:
    body = json.dumps({"model": "m", "choices": [{"message": {"content": content}}]}).encode()
    response = io.BytesIO(body)
    response.__enter__ = lambda self=response: self  # type: ignore[attr-defined]
    response.__exit__ = lambda *a: False  # type: ignore[attr-defined]
    return response


class _Ctx(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_provider_parses_fenced_json_and_retries_rate_limits(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def opener(request, timeout):
        calls.append(request)
        assert request.get_header("Authorization") == "Bearer secret-key"
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {"Retry-After": "1"}, None)
        body = json.dumps({"model": "m", "choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]}).encode()
        return _Ctx(body)
    provider = OpenAICompatibleProvider("http://localhost:1/v1", "m", "secret-key", max_retries=1, opener=opener)
    assert provider.complete_json("s", "u").data == {"a": 1}
    assert len(calls) == 2


def test_provider_reports_timeouts_and_bad_output(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def slow(request, timeout):
        raise TimeoutError()
    with pytest.raises(LLMError) as err:
        OpenAICompatibleProvider("http://localhost:1/v1", "m", None, max_retries=1, opener=slow).complete_json("s", "u")
    assert err.value.kind == "timeout"

    def prose(request, timeout):
        return _Ctx(json.dumps({"choices": [{"message": {"content": "I cannot do that."}}]}).encode())
    with pytest.raises(LLMError) as err:
        OpenAICompatibleProvider("http://localhost:1/v1", "m", None, opener=prose).complete_json("s", "u")
    assert err.value.kind == "invalid_output"
    with pytest.raises(LLMError):
        parse_json_object("[1, 2]")


# =================================================================================================
# Evaluation
# =================================================================================================


def _entry(entries, prefix):
    return next(e for e in entries if e.text.startswith(prefix))


def _evaluate(entry, answer):
    return evaluate_answer(ENGINE, question=entry.text, question_type=entry.question_type, answer=answer,
                           reference=entry.reference_answer, key_points=entry.key_points,
                           misconceptions=entry.misconceptions)


def _agreement(entries, path):
    data = json.loads(path.read_text(encoding="utf-8"))
    passed = 0
    for case in data["cases"]:
        result = _evaluate(_entry(entries, case["q"]), case["answer"])
        dims = {d.key: d.score for d in result.dimensions}
        values = {"overall": result.overall_score, "relevance": dims["relevance"],
                  "correctness": dims["correctness"], "specificity": dims["specificity"]}
        ok = True
        for key, bound in data["labels"][case["label"]].items():
            name, kind = key.rsplit("_", 1)
            value = values[name]
            if value is None:
                value = 0 if kind == "max" else 100
            ok &= value >= bound if kind == "min" else value <= bound
        passed += ok
    return passed / len(data["cases"])


def test_labelled_benchmark_agreement(bank_entries):  # noqa: F811
    # Regression guards, set just below the measured values (dev 0.93, held-out 0.70 with the lexical engine).
    # The held-out set was never used for tuning. Neither number measures real-world accuracy.
    assert _agreement(bank_entries, DATA / "eval_cases.json") >= 0.90
    assert _agreement(bank_entries, DATA / "eval_cases_holdout.json") >= 0.68


def test_keyword_list_is_mentioned_not_demonstrated(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "What is overfitting")
    result = _evaluate(entry, "Overfitting, training data, validation, cross-validation, regularization, dropout, "
                              "early stopping, test set, noise, generalization.")
    statuses = {c["status"] for c in result.concept_evidence}
    assert "demonstrated" not in statuses and "mentioned" in statuses
    assert result.evidence_level == "limited"
    assert next(d for d in result.dimensions if d.key == "correctness").score <= 50


def test_different_wording_gets_credit_with_quoted_evidence(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "What is overfitting")
    answer = ("A model overfits when it memorises quirks of its training set, so it does great there but badly on "
              "unseen data. I spot it when the held-out score is much worse than the training score, using k-fold "
              "checks. To avoid it I use weight decay or dropout and stop training once the validation loss starts "
              "rising, and I keep a final test set untouched.")
    result = _evaluate(entry, answer)
    demonstrated = [c for c in result.concept_evidence if c["status"] == "demonstrated"]
    assert len(demonstrated) >= 4
    assert all(c["evidence"].rstrip("…") in answer or answer.startswith(c["evidence"][:40]) for c in demonstrated)
    assert next(d for d in result.dimensions if d.key == "correctness").score >= 70


def test_incorrect_claim_is_distinguished_from_missing_evidence(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "Explain the bias-variance trade-off")
    wrong = _evaluate(entry, "High bias means the model overfits the training data and high variance means it "
                             "underfits. Adding complexity always reduces both bias and variance.")
    assert wrong.incorrect_claims and wrong.incorrect_claims[0]["evidence"]
    incomplete = _evaluate(entry, "Bias is error from a model that is too simple. I would look at the validation error.")
    assert not incomplete.incorrect_claims
    assert next(d for d in wrong.dimensions if d.key == "correctness").score < \
        next(d for d in incomplete.dimensions if d.key == "correctness").score


def test_unsupported_claims_are_flagged_but_correct_rules_are_not(bank_entries):  # noqa: F811
    q = _entry(bank_entries, "How would you handle an imbalanced dataset")
    flagged = _evaluate(q, "Imbalance doesn't matter for modern models. XGBoost always handles it perfectly by itself, "
                           "trust me.")
    assert flagged.unsupported_claims
    loop = _entry(bank_entries, "Explain how the browser event loop")
    fine = _evaluate(loop, "JavaScript runs on a single thread with a call stack. The event loop always runs all "
                           "microtasks before the next task, and the browser renders between tasks, so long "
                           "synchronous code blocks the page.")
    assert not fine.unsupported_claims


def test_brief_answer_reports_insufficient_evidence(bank_entries):  # noqa: F811
    result = _evaluate(_entry(bank_entries, "What is overfitting"), "It depends on the data.")
    assert result.evidence_level == "insufficient"
    assert "not shown yet" in result.explanation


def test_every_dimension_is_bounded_and_explained(bank_entries):  # noqa: F811
    for entry in bank_entries:
        if entry.kind is not QuestionKind.GENERIC:
            continue
        result = _evaluate(entry, entry.reference_answer)
        assert all(d.score is None or 0 <= d.score <= 100 for d in result.dimensions)
        assert all(d.explanation for d in result.dimensions) and 0 <= result.overall_score <= 100
        assert result.evidence_level in ("sufficient", "limited", "insufficient")


# --- bounded LLM review ------------------------------------------------------------------------


def test_llm_review_is_bounded_and_quote_verified(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "What is overfitting")
    answer = "Overfitting is when the model memorises noise. I compare training and validation results to see it."
    result = _evaluate(entry, answer)
    before = {d.key: d.score for d in result.dimensions}
    review = EvaluationReview(
        concepts=[
            {"concept": "early stopping", "status": "demonstrated", "quote": "I stop training early"},  # not in answer
            {"concept": "Training versus validation gap", "status": "demonstrated",
             "quote": "I compare training and validation results"},
            {"concept": "quantum", "status": "demonstrated", "quote": "noise"},  # not a rubric concept
        ],
        coverage_score=100, accuracy_score=100, suggestions=["Mention cross-validation."])
    applied = apply_review(result, review, answer=answer, key_points=entry.key_points, keyword_list=False)
    after = {d.key: d.score for d in result.dimensions}
    assert applied["upgraded_concepts"] in ([], ["training versus validation gap"])
    assert "early stopping" not in result.demonstrated_concepts
    assert after["coverage"] - before["coverage"] <= 15 and after["correctness"] - before["correctness"] <= 15
    assert any(s.startswith("Model suggestion:") for s in result.suggestions)
    assert result.evidence_level == "limited"  # the review disagreed by more than 20 points


def test_llm_review_cannot_raise_accuracy_over_an_incorrect_claim(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "Explain the bias-variance trade-off")
    answer = "High bias means the model overfits the training data. I would use a validation set."
    result = _evaluate(entry, answer)
    before = next(d for d in result.dimensions if d.key == "correctness").score
    apply_review(result, EvaluationReview(coverage_score=90, accuracy_score=95), answer=answer,
                 key_points=entry.key_points, keyword_list=False)
    assert next(d for d in result.dimensions if d.key == "correctness").score <= before


# =================================================================================================
# Coaching
# =================================================================================================


def _ev(score, skills=("SQL",), interview="i1", level="sufficient"):
    return AnswerEvidence(interview_id=interview, question_text=f"Question about {skills[0]}", question_type="technical",
                          category="core", focus_skills=list(skills), overall=score,
                          dimensions={"coverage": score, "correctness": score, "structure": 70}, evidence_level=level)


def _build(current, history=(), profile=("SQL",)):
    return build_plan(interview_id="i2", target_role="Backend Developer", required_skills=["SQL", "Docker"],
                      job_skills=[], profile_skills=list(profile), current=list(current), history=list(history),
                      previous_plan=None, previous_overall=None, current_overall=50, practice_pool=[])


def test_brief_answers_are_not_weaknesses():
    plan = _build([_ev(10, level="insufficient"), _ev(15, level="insufficient")])
    assert plan["weaknesses"] == []
    assert plan["insufficient_evidence"][0]["name"] == "SQL"


def test_consistent_strengths_and_evidence_links():
    plan = _build([_ev(90, interview="i2")], history=[_ev(85, interview="i1")])
    strength = plan["strengths"][0]
    assert strength["consistent"] is True and strength["interviews"] == 2
    weak = _build([_ev(30, interview="i2")], history=[_ev(35, interview="i1")])["weaknesses"][0]
    assert weak["status"] == "gap" and weak["examples"][0]["question"].startswith("Question about SQL")


def test_competency_overview_separates_profile_from_interview_evidence():
    plan = _build([_ev(30)], profile=("SQL",))
    row = next(c for c in plan["competencies"] if c["name"] == "SQL")
    assert row["in_profile"] is True and row["interview_status"] == "needs_evidence"
    docker = next(c for c in plan["competencies"] if c["name"] == "Docker")
    assert docker["interview_status"] == "unassessed" and docker["in_profile"] is False
    assert plan["version"] == "plan-v2"


# =================================================================================================
# API integration
# =================================================================================================

VAGUE = ("I think it mostly depends on the situation and on the team, so I would probably search online first and "
         "then decide later what to do about it with my manager.")


def test_adaptive_interview_persists_agent_decisions(client, user_a, api_session_factory):
    from sqlalchemy import select

    from app.models import AgentDecisionRecord

    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"], adaptive=True).json()
    q = interview["questions"][0]
    body = answer_and_evaluate(client, user_a, interview["id"], q["id"], text=VAGUE)
    decision = body["agent_decision"]
    assert decision["source"] == "rules" and decision["policy"] == "accepted" and decision["rationale"]
    assert body["follow_up"] is not None and decision["action"] in ("probe_concept", "request_example", "clarify")
    assert body["evidence_level"] in ("insufficient", "limited", "sufficient") and isinstance(body["concept_evidence"], list)
    again = client.get(f"/api/v1/interviews/{interview['id']}/questions/{q['id']}/evaluation", headers=user_a).json()
    assert again["agent_decision"] == decision
    with api_session_factory() as db:
        rows = list(db.scalars(select(AgentDecisionRecord)))
        assert len(rows) == 1 and str(rows[0].result_question_id) == body["follow_up"]["id"]


def test_fixed_interview_records_no_decisions(client, user_a, api_session_factory):
    from sqlalchemy import select

    from app.models import AgentDecisionRecord

    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    body = answer_and_evaluate(client, user_a, interview["id"], interview["questions"][0]["id"], text=VAGUE)
    assert body["agent_decision"] is None and body["follow_up"] is None
    with api_session_factory() as db:
        assert list(db.scalars(select(AgentDecisionRecord))) == []


def test_llm_follow_up_is_validated_and_marked_as_llm(client, user_a):
    class ApiGateway(FakeGateway):
        def call(self, feature, system, user, schema, max_tokens=700):
            if feature != "agent":
                from app.llm.gateway import LLMCallResult
                return LLMCallResult(None, "feature_off")
            return super().call(feature, system, user, schema, max_tokens)

    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"], adaptive=True).json()
    q = interview["questions"][0]
    set_llm_for_tests(ApiGateway({"action": "request_example", "rationale": "The answer stayed general.",
                                  "follow_up_question": f"Can you give a concrete example related to: {q['text'][:60]}?"}))
    body = answer_and_evaluate(client, user_a, interview["id"], q["id"], text=VAGUE)
    assert body["agent_decision"]["source"] == "llm" and body["follow_up"]["text"].startswith("Can you give a concrete")


def test_health_reports_intelligence_mode(client):
    body = client.get("/api/v1/health").json()
    assert body["intelligence"]["llm"] == "disabled" and body["intelligence"]["embeddings"] == "lexical"


def test_weak_interview_never_changes_the_confirmed_profile(client, user_a):
    from tests.factories import make_pdf
    from tests.test_intelligence import CV_LINES

    cv = upload_cv(client, user_a, data=make_pdf(CV_LINES)).json()["cv"]
    profile = client.get("/api/v1/profile", headers=user_a).json()["profile"]
    confirmed = client.put("/api/v1/profile", headers=user_a, json={"profile": profile, "confirm": True}).json()
    interview = create_interview(client, user_a, cv["id"]).json()
    for q in interview["questions"]:
        answer_and_evaluate(client, user_a, interview["id"], q["id"], text=VAGUE)
    client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=user_a)
    after = client.get("/api/v1/profile", headers=user_a).json()
    assert after["profile"]["technical_skills"] == confirmed["profile"]["technical_skills"]
    assert after["status"] == "confirmed"


def test_agent_decisions_are_private(client, user_a, user_b):
    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"], adaptive=True).json()
    q = interview["questions"][0]
    answer_and_evaluate(client, user_a, interview["id"], q["id"], text=VAGUE)
    base = f"/api/v1/interviews/{interview['id']}"
    assert client.get(f"{base}/questions/{q['id']}/evaluation", headers=user_b).status_code == 404
    assert client.get(base, headers=user_b).status_code == 404


def test_old_evaluations_without_evidence_still_render(client, user_a, api_session_factory):
    from sqlalchemy import select

    from app.models import Evaluation

    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    q = interview["questions"][0]
    answer_and_evaluate(client, user_a, interview["id"], q["id"])
    with api_session_factory() as db:  # simulate an evaluation stored before Milestone 5 (and before Milestone 4)
        ev = db.scalar(select(Evaluation))
        ev.concept_evidence, ev.unsupported_claims, ev.incorrect_claims, ev.evidence_level = [], [], [], None
        ev.dimensions = None
        db.commit()
    body = client.get(f"/api/v1/interviews/{interview['id']}/questions/{q['id']}/evaluation", headers=user_a).json()
    assert body["concept_evidence"] == [] and body["evidence_level"] is None
    assert {d["key"] for d in body["dimensions"]} >= {"relevance", "structure", "communication"}


def test_agent_module_exposes_documented_actions():
    assert set(agent_mod.ACTIONS) == {"continue", "clarify", "request_example", "probe_concept", "deepen"}
    assert validate(propose_rules(_ctx()), _ctx()) is None
    assert competency_model().get("Python") is not None
    assert build_profile("Skills\nPython").technical_skills[0].name == "Python"


def test_off_topic_llm_follow_up_is_rejected_even_when_it_shares_a_generic_word():
    ctx = _ctx(question_text="Tell me about a time you disagreed with a teammate on a technical decision.",
               question_type=QuestionType.BEHAVIORAL, key_points=["the situation and disagreement", "using evidence"],
               focus_skills=["Teamwork"], missing=["using evidence"], overall=40)
    d = decide(ctx, FakeGateway({"action": "clarify", "rationale": "ok ok",
                                 "follow_up_question": "What is your favourite football team and why?"}))
    assert d.source == "rules" and d.llm_status == "rejected:off_topic"
    on_topic = decide(ctx, FakeGateway({"action": "request_example", "rationale": "ok ok",
                                        "follow_up_question": "What evidence did you use to resolve the disagreement?"}))
    assert on_topic.source == "llm"


def test_question_and_its_follow_up_count_as_one_piece_of_evidence():
    parent = _ev(30)
    parent.group = "q1"
    follow = _ev(40)
    follow.group, follow.category = "q1", "follow_up"
    weak = _build([parent, follow])["weaknesses"][0]
    assert weak["status"] == "needs_evidence" and weak["evidence_count"] == 1
