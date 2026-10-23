"""Milestone 4: candidate profile, personalised selection, adaptive follow-ups,
multi-dimensional evaluation and improvement plans.

All tests run without embeddings or any external AI provider (SIMILARITY_BACKEND=lexical).
"""

import pytest

from app.intelligence import adaptive
from app.intelligence.improvement import AnswerEvidence, build_plan
from app.intelligence.profile_extraction import build_profile
from app.models.enums import Difficulty, InterviewType, QuestionKind, QuestionType
from app.scoring.scorer import compute_signals, evaluate_answer
from app.scoring.similarity import LexicalSimilarity
from app.services.question_selection import select_questions
from tests.factories import make_pdf
from tests.helpers import answer_and_evaluate, create_interview, upload_cv
from tests.test_scoring_and_selection import _bank_items, bank_entries  # noqa: F401  (fixture)

ENGINE = LexicalSimilarity()
PROFILE_URL = "/api/v1/profile"

CV_LINES = [
    "Sara Example",
    "Machine Learning Engineer",
    "Summary",
    "Final-year computer science student who enjoys teamwork and communicating results to stakeholders.",
    "Skills",
    "Python, sklearn, PyTorch, Postgres, K8s, Docker, Git",
    "Experience",
    "ML Intern - Example Analytics (Jun 2024 - Sep 2024)",
    "- Built a ticket classifier with scikit-learn that reduced triage time by 30%.",
    "Education",
    "B.Sc. Computer Science - Example University (2021 - 2025)",
    "Projects",
    "Interview Coach - FastAPI and React app for interview practice.",
]
CV_TEXT = "\n".join(CV_LINES)
WEAK_ANSWER = "I am not sure. I think it is something about computers and data, it depends."
WEAK_ANSWERS_SET = [WEAK_ANSWER, "Maybe it works, I would need to look it up.", "It is a common thing that people use."]
# Milestone 5: answers this brief are "insufficient evidence", not weaknesses. These are
# substantive enough to judge, and still weak.
VAGUE_ANSWERS_SET = [
    "I think it mostly depends on the situation and on the team, so I would probably search online first and "
    "then decide later what to do about it with my manager.",
    "Honestly I have not used this much. I would read some articles about it and try things until something works, "
    "and then I would ask a colleague if it still does not work.",
]


def _skills(profile) -> dict[str, str]:
    return {s.name: s.source for s in profile.technical_skills}


# --- 1. profile extraction ---------------------------------------------------------------------


def test_profile_extraction_separates_extracted_and_inferred_and_normalises_synonyms():
    profile = build_profile(CV_TEXT)
    skills = _skills(profile)
    # synonyms are normalised to one canonical name each
    assert {"scikit-learn", "PostgreSQL", "Kubernetes", "Python", "PyTorch"} <= set(skills)
    assert not {"sklearn", "Postgres", "K8s"} & set(skills)
    assert set(skills.values()) == {"extracted"}
    assert all(s.evidence for s in profile.technical_skills)  # every extracted item shows where it came from
    for value in (profile.target_role, profile.experience_level, profile.years_experience):
        assert value.source == "inferred" and value.evidence
    assert profile.target_role.value == "Machine Learning Engineer"
    assert profile.experience_level.value == "student"
    assert [e.organization for e in profile.experience] == ["Example Analytics"]
    assert profile.projects[0].name == "Interview Coach"
    assert {"Teamwork", "Communication"} <= {s.name for s in profile.soft_skills}


@pytest.mark.parametrize("text", ["", None, "asdf qwerty ;;; 12345 ????\n\n lorem"])
def test_malformed_or_empty_cv_gives_empty_profile_with_warnings_and_invents_nothing(text):
    profile = build_profile(text)
    assert profile.technical_skills == [] and profile.experience == [] and profile.education == []
    assert profile.projects == [] and profile.achievements == []
    assert profile.target_role.value is None and profile.experience_level.value is None
    assert any("could not be determined" in w for w in profile.warnings)


def test_missing_sections_are_reported_not_invented():
    profile = build_profile("Skills\nPython, SQL and Docker.")
    assert set(_skills(profile)) == {"Python", "SQL", "Docker"}
    assert profile.experience == [] and profile.education == [] and profile.projects == []
    joined = " ".join(profile.warnings)
    assert "No Experience section" in joined and "No Education section" in joined


def test_explicit_target_role_wins_over_inference():
    profile = build_profile(CV_TEXT, explicit_target_role="Data Scientist")
    assert profile.target_role.value == "Data Scientist"


# --- 2. profile review / editing (API) -------------------------------------------------------


def test_profile_is_built_on_upload_as_a_draft(client, user_a):
    assert client.get(PROFILE_URL, headers=user_a).json()["error"]["code"] == "PROFILE_NOT_FOUND"
    upload_cv(client, user_a, data=make_pdf(CV_LINES))
    body = client.get(PROFILE_URL, headers=user_a).json()
    assert body["status"] == "draft" and body["confirmed_at"] is None
    names = {s["name"] for s in body["profile"]["technical_skills"]}
    assert {"scikit-learn", "Kubernetes"} <= names


def test_profile_edit_recomputes_provenance_and_confirms(client, user_a):
    upload_cv(client, user_a, data=make_pdf(CV_LINES))
    profile = client.get(PROFILE_URL, headers=user_a).json()["profile"]
    profile["technical_skills"] = [s for s in profile["technical_skills"] if s["name"] != "Kubernetes"]
    # a client cannot claim an item it added was extracted from the CV
    profile["technical_skills"].append({"name": "k8s", "source": "extracted", "evidence": "fake"})
    profile["technical_skills"].append({"name": "Terraform", "source": "extracted"})
    profile["experience_level"] = {"value": "junior", "source": "inferred"}

    response = client.put(PROFILE_URL, headers=user_a, json={"profile": profile, "confirm": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "confirmed" and body["confirmed_at"]
    skills = {s["name"]: s for s in body["profile"]["technical_skills"]}
    assert skills["Kubernetes"]["source"] == "user"  # re-added under its alias: normalised, marked as user
    assert skills["Terraform"]["source"] == "user"
    assert skills["Python"]["source"] == "extracted"  # untouched items keep their provenance
    assert body["profile"]["experience_level"]["source"] == "user"


def test_profile_rejects_invalid_values(client, user_a):
    upload_cv(client, user_a, data=make_pdf(CV_LINES))
    profile = client.get(PROFILE_URL, headers=user_a).json()["profile"]
    profile["experience_level"] = {"value": "wizard"}
    assert client.put(PROFILE_URL, headers=user_a, json={"profile": profile}).status_code == 422
    profile["experience_level"] = {"value": "junior"}
    profile["unexpected"] = "x"
    assert client.put(PROFILE_URL, headers=user_a, json={"profile": profile}).status_code == 422


def test_rebuild_keeps_user_added_items(client, user_a):
    upload_cv(client, user_a, data=make_pdf(CV_LINES))
    profile = client.get(PROFILE_URL, headers=user_a).json()["profile"]
    profile["technical_skills"].append({"name": "Terraform"})
    client.put(PROFILE_URL, headers=user_a, json={"profile": profile, "confirm": True})
    rebuilt = client.post(f"{PROFILE_URL}/rebuild", headers=user_a).json()
    assert rebuilt["status"] == "draft"  # a re-extraction must be reviewed again
    assert "Terraform" in {s["name"] for s in rebuilt["profile"]["technical_skills"]}


def test_only_a_confirmed_profile_personalises_interviews(client, user_a):
    cv = upload_cv(client, user_a, data=make_pdf(CV_LINES)).json()["cv"]
    draft = create_interview(client, user_a, cv["id"], target_role="Machine Learning Engineer", question_count=10)
    assert draft.json()["config"]["personalized"] is False
    assert all(q["category"] != "project" for q in draft.json()["questions"])

    profile = client.get(PROFILE_URL, headers=user_a).json()["profile"]
    client.put(PROFILE_URL, headers=user_a, json={"profile": profile, "confirm": True})
    personal = create_interview(client, user_a, cv["id"], target_role="Machine Learning Engineer",
                                interview_type="mixed", question_count=10).json()
    assert personal["config"]["personalized"] is True
    assert any(q["category"] == "project" and "Interview Coach" in q["text"] for q in personal["questions"])
    assert all(q["reason"] for q in personal["questions"])


# --- 3. selection: ranking, no duplicates, no embeddings ---------------------------------------


def _select(bank_entries, **overrides):  # noqa: F811
    kwargs = dict(target_role="Machine Learning Engineer", interview_type=InterviewType.MIXED,
                  difficulty=Difficulty.INTERMEDIATE, question_count=15, cv_skills=["Python", "Docker"],
                  seed="fixed-seed", profile=build_profile(CV_TEXT), engine=ENGINE) | overrides
    return select_questions(_bank_items(bank_entries), **kwargs)


@pytest.mark.parametrize("count", [5, 10, 15])
def test_personalised_selection_has_no_duplicates_and_explains_every_choice(bank_entries, count):  # noqa: F811
    selected = _select(bank_entries, question_count=count)
    assert len(selected) == count
    assert len({q.text.lower() for q in selected}) == count
    assert len({q.bank_question_id for q in selected}) == count
    assert all(q.reason and q.category for q in selected)
    assert all("{" not in q.text for q in selected)  # templates are always filled in


def test_selection_is_deterministic(bank_entries):  # noqa: F811
    first = [(q.text, q.reason) for q in _select(bank_entries)]
    assert first == [(q.text, q.reason) for q in _select(bank_entries)]


def test_selection_works_without_embeddings_or_an_llm(bank_entries, monkeypatch):  # noqa: F811
    # No engine passed and the configured backend unavailable: the lexical fallback is used.
    from app.scoring import similarity

    calls = []

    def unavailable():
        calls.append(1)
        raise similarity.EngineUnavailable("sentence-transformers not installed")
    monkeypatch.setattr(similarity, "get_engine", unavailable)
    selected = _select(bank_entries, engine=None, question_count=10)
    assert calls  # the configured engine was tried, and the lexical fallback took over
    assert len(selected) == 10 and len({q.text for q in selected}) == 10


def test_role_and_job_description_drive_the_ranking(bank_entries):  # noqa: F811
    selected = _select(bank_entries, interview_type=InterviewType.TECHNICAL, question_count=10, profile=None,
                       cv_skills=[], job_description="We need strong Kubernetes and Docker experience.")
    covered = {s for q in selected for s in q.focus_skills}
    assert {"Kubernetes", "Docker"} & covered
    assert any("job description" in q.reason.lower() for q in selected)


def test_fixed_interview_still_respects_requested_type(bank_entries):  # noqa: F811
    selected = _select(bank_entries, interview_type=InterviewType.BEHAVIORAL, question_count=5)
    assert {q.question_type for q in selected} == {QuestionType.BEHAVIORAL}


# --- 4. adaptive follow-ups ---------------------------------------------------------------------


def _decide(**overrides):
    kwargs = dict(question_text="Q?", question_type=QuestionType.TECHNICAL, category="core", parent_reference="ref",
                  focus_skills=["Python"], overall=30, dimensions=[{"key": "specificity", "score": 20}],
                  missing_concepts=["regularization"], used=0, limit=2, has_follow_up=False) | overrides
    return adaptive.decide_follow_up(**kwargs)


def test_follow_up_rules():
    assert _decide().kind == "clarify" and "regularization" in _decide().text
    assert _decide(question_type=QuestionType.BEHAVIORAL).kind == "example"
    assert _decide(overall=60, dimensions=[{"key": "specificity", "score": 20}]).kind == "example"
    assert _decide(overall=90).kind == "deeper"
    assert _decide(overall=65, dimensions=[{"key": "specificity", "score": 70}]) is None


@pytest.mark.parametrize("overrides", [{"used": 2}, {"has_follow_up": True}, {"category": "follow_up"}])
def test_follow_up_limits(overrides):
    assert _decide(**overrides) is None


@pytest.mark.parametrize(("count", "limit"), [(5, 2), (10, 3), (15, 4)])
def test_follow_up_limit_per_interview_length(count, limit):
    assert adaptive.max_follow_ups(count) == limit


def test_adaptive_interview_inserts_follow_ups_up_to_the_limit(client, user_a):
    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"], adaptive=True).json()
    assert interview["config"]["adaptive"] is True and interview["config"]["max_follow_ups"] == 2
    iid = interview["id"]
    follow_ups = []
    for _ in range(20):  # answer whatever is next, always weakly
        state = client.get(f"/api/v1/interviews/{iid}", headers=user_a).json()
        pending = [q for q in state["questions"] if q["state"] != "evaluated"]
        if not pending:
            break
        evaluation = answer_and_evaluate(client, user_a, iid, pending[0]["id"], text=WEAK_ANSWER)
        if evaluation["follow_up"]:
            follow_up = evaluation["follow_up"]
            assert follow_up["parent_question_id"] == pending[0]["id"]
            assert follow_up["category"] == "follow_up" and follow_up["follow_up_kind"] in ("clarify", "example")
            assert follow_up["position"] == pending[0]["position"] + 1  # asked right after its parent
            follow_ups.append(follow_up)
            # repeating the evaluation is idempotent: it returns the same follow-up, never a second one
            again = client.post(f"/api/v1/interviews/{iid}/questions/{pending[0]['id']}/evaluation", headers=user_a)
            assert again.status_code == 200 and again.json()["follow_up"]["id"] == follow_up["id"]
    state = client.get(f"/api/v1/interviews/{iid}", headers=user_a).json()
    assert len(follow_ups) == 2
    assert len(state["questions"]) == 5 + 2
    assert [q["position"] for q in state["questions"]] == list(range(1, 8))
    assert not any(q["parent_question_id"] in {f["id"] for f in follow_ups} for q in state["questions"])  # no chains
    results = client.post(f"/api/v1/interviews/{iid}/complete", headers=user_a)
    assert results.status_code == 200
    assert sum(1 for i in results.json()["items"] if i["question"]["parent_question_id"]) == 2


def test_fixed_interview_flow_is_unchanged(client, user_a):
    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    assert interview["config"]["adaptive"] is False and interview["config"]["max_follow_ups"] == 0
    before = [(q["id"], q["text"], q["position"]) for q in interview["questions"]]
    for q in interview["questions"]:
        evaluation = answer_and_evaluate(client, user_a, interview["id"], q["id"], text=WEAK_ANSWER)
        assert evaluation["follow_up"] is None and evaluation["replaced_question"] is None
    state = client.get(f"/api/v1/interviews/{interview['id']}", headers=user_a).json()
    assert [(q["id"], q["text"], q["position"]) for q in state["questions"]] == before


def test_target_difficulty_rules():
    assert adaptive.target_difficulty([90], Difficulty.INTERMEDIATE) is None  # not enough evidence
    assert adaptive.target_difficulty([90, 85], Difficulty.INTERMEDIATE) is Difficulty.ADVANCED
    assert adaptive.target_difficulty([30, 40], Difficulty.INTERMEDIATE) is Difficulty.BEGINNER
    assert adaptive.target_difficulty([90, 90], Difficulty.ADVANCED) is None
    assert adaptive.target_difficulty([60, 65], Difficulty.INTERMEDIATE) is None


# --- 5. evaluation ------------------------------------------------------------------------------

DIMENSIONS = {"relevance", "coverage", "correctness", "structure", "specificity", "communication"}


def _entry(bank_entries, text):  # noqa: F811
    return next(e for e in bank_entries if e.text.startswith(text))


def _evaluate(entry, answer):
    return evaluate_answer(ENGINE, question=entry.text, question_type=entry.question_type, answer=answer,
                           reference=entry.reference_answer, key_points=entry.key_points,
                           misconceptions=entry.misconceptions)


def test_every_evaluation_has_valid_dimensions_and_an_explanation(bank_entries):  # noqa: F811
    for entry in bank_entries:
        if entry.kind is not QuestionKind.GENERIC:
            continue
        for answer in (entry.reference_answer, WEAK_ANSWER):
            result = _evaluate(entry, answer)
            dims = {d.key: d for d in result.dimensions}
            assert set(dims) == DIMENSIONS
            assert all(d.score is None or 0 <= d.score <= 100 for d in dims.values())
            assert all(d.explanation for d in dims.values())
            assert abs(sum(d.weight for d in dims.values() if d.score is not None) - 1) < 0.01
            assert 0 <= result.overall_score <= 100 and result.explanation
            assert set(result.missing_concepts) <= set(entry.key_points)
            if entry.question_type is QuestionType.BEHAVIORAL:
                assert dims["correctness"].score is None  # no technical accuracy claim for stories


def test_similarity_alone_cannot_produce_a_high_correctness_score(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "What is overfitting")
    # Same vocabulary as the reference, but as a bare list of terms and with a misconception.
    keyword_salad = ("overfitting, training data, validation, cross-validation, regularization, dropout, "
                     "early stopping, test set, noise, model")
    wrong = ("Overfitting means the model is too simple, so it has high bias on training data and validation data. "
             "More training accuracy always means a better model, so I add layers and train longer.")
    for answer in (keyword_salad, wrong):
        signals = compute_signals(ENGINE, question=entry.text, question_type=entry.question_type, answer=answer,
                                  reference=entry.reference_answer, key_points=entry.key_points, extra_terms=[],
                                  misconceptions=entry.misconceptions)
        assert signals.sim_ref > 0.2  # the wording is clearly similar...
        result = _evaluate(entry, answer)
        correctness = next(d for d in result.dimensions if d.key == "correctness")
        assert correctness.score <= 50, (answer, correctness)  # ...but that does not make it correct
    wrong_result = _evaluate(entry, wrong)
    assert any("underfitting" in s.lower() or "training accuracy" in s.lower()
               for s in [*wrong_result.weaknesses, *wrong_result.suggestions])
    assert _evaluate(entry, entry.reference_answer).overall_score >= wrong_result.overall_score + 30


def test_correct_answer_in_different_words_still_gets_credit(bank_entries):  # noqa: F811
    entry = _entry(bank_entries, "What is overfitting")
    paraphrase = ("A model overfits when it memorises noise in its training set, so it does great there but badly "
                  "on unseen data. I spot it when the held-out score is much worse than the training score, using "
                  "k-fold checks and learning curves. To avoid it I use weight decay or dropout, stop training early "
                  "when the validation loss rises, and keep a final test set untouched.")
    result = _evaluate(entry, paraphrase)
    assert next(d for d in result.dimensions if d.key == "correctness").score >= 70
    assert result.overall_score >= 65


def test_evaluation_api_is_backwards_compatible_and_adds_detail(client, user_a):
    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    body = answer_and_evaluate(client, user_a, interview["id"], interview["questions"][0]["id"])
    assert set(body["category_scores"]) == {"relevance", "clarity", "technical_depth", "structure"}
    assert {d["key"] for d in body["dimensions"]} == DIMENSIONS
    assert body["explanation"] and isinstance(body["suggestions"], list) and body["ideal_outline"]
    assert "not as proof of correctness" in body["explanation"] or "estimate" in body["explanation"].lower()


# --- 6. improvement plan ------------------------------------------------------------------------


def _evidence(score, skills=("Python",), interview="i1", dims=None):
    return AnswerEvidence(interview_id=interview, question_text="q", question_type="technical", category="core",
                          focus_skills=list(skills), overall=score,
                          dimensions=dims or {"coverage": score, "correctness": score, "structure": 70})


def _plan(current, history=(), required=("Python", "Docker"), profile_skills=("Python",)):
    return build_plan(interview_id="i2", target_role="Backend Developer", required_skills=list(required),
                      job_skills=[], profile_skills=list(profile_skills), current=list(current), history=list(history),
                      previous_plan=None, previous_overall=None, current_overall=50, practice_pool=[
                          {"bank_question_id": "b1", "text": "Explain Python generators.", "type": "technical",
                           "skill_tags": ["Python"]}])


def test_one_weak_answer_is_not_called_a_gap():
    plan = _plan([_evidence(30)])
    (weak,) = plan["weaknesses"]
    assert weak["name"] == "Python" and weak["status"] == "needs_evidence"
    assert not any(step["title"].startswith("Strengthen") for step in plan["next_steps"])


def test_repeated_weak_answers_are_a_gap_with_practice_and_next_step():
    plan = _plan([_evidence(30)], history=[_evidence(35, interview="i0")])
    (weak,) = plan["weaknesses"]
    assert weak["status"] == "gap" and weak["evidence_count"] == 2
    assert plan["next_steps"][0]["title"] == "Strengthen Python" and plan["next_steps"][0]["priority"] == "high"
    assert plan["practice_questions"][0]["bank_question_id"] == "b1"


def test_unassessed_required_skill_is_not_demonstrated_not_a_weakness():
    plan = _plan([_evidence(90)])
    assert {"skill": "Docker", "status": "not_demonstrated", "required_by": "Backend Developer"} in \
        plan["role_skills_to_practice"]
    assert plan["weaknesses"] == []
    assert plan["strengths"][0]["name"] == "Python"


def test_project_questions_are_not_treated_as_skills():
    project = AnswerEvidence(interview_id="i1", question_text="q", question_type="technical", category="project",
                             focus_skills=["Interview Coach"], overall=20, dimensions={"structure": 20})
    plan = _plan([project, project])
    assert all(w["name"] != "Interview Coach" for w in plan["weaknesses"])
    assert any(s["name"] == "Structure" for s in plan["scores"])  # still counted for the dimensions


def test_repeated_pattern_needs_several_answers():
    low_structure = {"coverage": 80, "correctness": 80, "structure": 20}
    assert _plan([_evidence(80, dims=low_structure)])["patterns"] == []
    plan = _plan([_evidence(80, dims=low_structure), _evidence(80, dims=low_structure)])
    assert plan["patterns"][0]["dimension"] == "structure"


def test_plan_api_reflects_results_and_tracks_progress(client, user_a):
    cv = upload_cv(client, user_a).json()["cv"]
    ids = []
    for answers in (VAGUE_ANSWERS_SET, None):
        interview = create_interview(client, user_a, cv["id"]).json()
        for i, q in enumerate(interview["questions"]):
            kwargs = {"text": answers[i % len(answers)]} if answers else {}
            answer_and_evaluate(client, user_a, interview["id"], q["id"], **kwargs)
        client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=user_a)
        ids.append(interview["id"])

    first = client.get(f"/api/v1/interviews/{ids[0]}/improvement-plan", headers=user_a).json()
    # Weak answers show up as weaknesses, or (Milestone 5) as "not enough evidence" when an answer was
    # off-topic or too brief to judge; the repeated patterns always reflect them.
    assert (first["plan"]["weaknesses"] or first["plan"]["insufficient_evidence"]) and first["plan"]["patterns"]
    assert first["plan"]["progress"]["overall"] is None
    latest = client.get("/api/v1/improvement-plans/latest", headers=user_a).json()
    assert latest["interview_id"] == ids[1]
    overall = latest["plan"]["progress"]["overall"]
    assert overall["change"] > 0 and overall["previous"] == first["plan"]["overall_score"]


def test_plan_needs_a_completed_interview(client, user_a):
    assert client.get("/api/v1/improvement-plans/latest", headers=user_a).json()["error"]["code"] == "PLAN_NOT_FOUND"
    cv = upload_cv(client, user_a).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    response = client.get(f"/api/v1/interviews/{interview['id']}/improvement-plan", headers=user_a)
    assert response.status_code == 409


# --- 7. per-user isolation -----------------------------------------------------------------------


def test_profiles_evaluations_and_plans_are_private(client, user_a, user_b):
    cv = upload_cv(client, user_a, data=make_pdf(CV_LINES)).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    qid = interview["questions"][0]["id"]
    answer_and_evaluate(client, user_a, interview["id"], qid)
    for q in interview["questions"][1:]:
        answer_and_evaluate(client, user_a, interview["id"], q["id"])
    client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=user_a)

    # B has no profile and cannot reach A's
    assert client.get(PROFILE_URL, headers=user_b).status_code == 404
    a_profile = client.get(PROFILE_URL, headers=user_a).json()
    client.put(PROFILE_URL, headers=user_b, json={"profile": a_profile["profile"]})
    assert client.get(PROFILE_URL, headers=user_a).json()["status"] == "draft"  # A's profile untouched
    # B cannot read A's evaluation or plan, and has no plan of their own
    base = f"/api/v1/interviews/{interview['id']}"
    assert client.get(f"{base}/questions/{qid}/evaluation", headers=user_b).status_code == 404
    assert client.get(f"{base}/improvement-plan", headers=user_b).status_code == 404
    assert client.get("/api/v1/improvement-plans/latest", headers=user_b).status_code == 404
    assert client.get(f"{base}/improvement-plan", headers=user_a).status_code == 200


def test_deleting_my_data_removes_profile_and_plans(client, user_a):
    cv = upload_cv(client, user_a, data=make_pdf(CV_LINES)).json()["cv"]
    interview = create_interview(client, user_a, cv["id"]).json()
    for q in interview["questions"]:
        answer_and_evaluate(client, user_a, interview["id"], q["id"])
    client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=user_a)
    assert client.get("/api/v1/improvement-plans/latest", headers=user_a).status_code == 200
    assert client.delete("/api/v1/users/me/data", headers=user_a).status_code in (200, 204)
    assert client.get(PROFILE_URL, headers=user_a).status_code == 404
    assert client.get("/api/v1/improvement-plans/latest", headers=user_a).status_code == 404
