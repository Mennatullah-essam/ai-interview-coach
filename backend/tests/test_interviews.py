"""Interview creation, answers, evaluations, completion, results, history and stats."""

import pytest
from sqlalchemy import select, update

from app.models import QuestionBankItem
from tests.factories import GOOD_TECHNICAL_ANSWER
from tests.helpers import answer_and_evaluate, create_interview, full_interview, upload_cv


@pytest.fixture
def cv_id(client, user_a):
    return upload_cv(client, user_a).json()["cv"]["id"]


def _url(interview, question=None, tail=""):
    base = f"/api/v1/interviews/{interview['id']}"
    return f"{base}/questions/{question['id']}{tail}" if question else f"{base}{tail}"


# --- creation ------------------------------------------------------------------------------


@pytest.mark.parametrize("count", [5, 10, 15])
@pytest.mark.parametrize("itype", ["technical", "behavioral", "mixed"])
def test_create_interview_returns_distinct_questions(client, user_a, cv_id, count, itype):
    response = create_interview(client, user_a, cv_id, interview_type=itype, question_count=count)

    assert response.status_code == 201, response.text
    body = response.json()
    questions = body["questions"]
    assert body["status"] == "in_progress"
    assert body["config"] == {"cv_id": cv_id, "target_role": "AI Engineer", "interview_type": itype,
                              "difficulty": "intermediate", "question_count": count,
                              # Milestone 4 additions; defaults keep the fixed (non-adaptive) flow
                              "adaptive": False, "max_follow_ups": 0, "personalized": False,
                              "has_job_description": False}
    assert [q["position"] for q in questions] == list(range(1, count + 1))
    assert len({q["text"] for q in questions}) == count
    types = {q["type"] for q in questions}
    assert types == ({"technical", "behavioral"} if itype == "mixed" else {itype})
    # Only public fields: Milestone 4 adds the selection explanation and follow-up links,
    # never the reference answer, key points or misconception patterns.
    assert set(questions[0]) == {"id", "position", "text", "type", "state", "category", "reason",
                                 "focus_skills", "parent_question_id", "follow_up_kind"}


def test_questions_never_reveal_reference_answers(client, user_a, cv_id, api_session_factory):
    interview = create_interview(client, user_a, cv_id).json()
    state = client.get(_url(interview), headers=user_a)
    with api_session_factory() as db:
        references = [q.ideal_answer for q in db.scalars(select(QuestionBankItem))]
    for reference in references:
        assert reference[:60] not in str(interview)
        assert reference[:60] not in state.text


def test_cv_skill_templates_are_filled_from_the_cv(client, user_a, cv_id):
    interview = create_interview(client, user_a, cv_id, question_count=15).json()
    texts = " ".join(q["text"] for q in interview["questions"])
    assert "{skill}" not in texts
    assert any(skill in texts for skill in ("Python", "PyTorch", "FastAPI", "Docker", "SQL", "React", "Git"))


def test_custom_role_falls_back_to_general_questions(client, user_a, cv_id):
    response = create_interview(client, user_a, cv_id, target_role="Underwater Basket Weaver", question_count=15)
    assert response.status_code == 201


@pytest.mark.parametrize(
    "override",
    [{"question_count": 7}, {"interview_type": "trivia"}, {"difficulty": "expert"},
     {"target_role": "AI"}, {"target_role": "x" * 101}],
)
def test_invalid_interview_config(client, user_a, cv_id, override):
    response = create_interview(client, user_a, cv_id, **override)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INTERVIEW_CONFIG"


def test_cv_required(client, user_a):
    response = create_interview(client, user_a, None)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CV_REQUIRED"


def test_unknown_cv_is_not_found(client, user_a):
    response = create_interview(client, user_a, "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CV_NOT_FOUND"


def test_too_small_bank_fails_instead_of_padding(client, user_a, cv_id, api_session_factory):
    with api_session_factory() as db:
        db.execute(update(QuestionBankItem).where(QuestionBankItem.question_type == "behavioral").values(is_active=False))
        db.commit()
    response = create_interview(client, user_a, cv_id, interview_type="behavioral")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTION_BANK_INSUFFICIENT"


# --- answers ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [("   ", "ANSWER_EMPTY"), ("Too short to grade.", "ANSWER_TOO_SHORT"), ("x" * 1501, "ANSWER_TOO_LONG")],
)
def test_answer_length_rules(client, user_a, cv_id, text, code):
    interview = create_interview(client, user_a, cv_id).json()
    response = client.put(_url(interview, interview["questions"][0], "/answer"), headers=user_a, json={"answer_text": text})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_answer_upsert_then_locked_after_evaluation(client, user_a, cv_id):
    interview = create_interview(client, user_a, cv_id).json()
    question = interview["questions"][0]
    url = _url(interview, question, "/answer")

    first = client.put(url, headers=user_a, json={"answer_text": "  " + GOOD_TECHNICAL_ANSWER + "  "})
    second = client.put(url, headers=user_a, json={"answer_text": GOOD_TECHNICAL_ANSWER + " Updated."})
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["answer_text"] == GOOD_TECHNICAL_ANSWER  # trimmed
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["char_count"] == len(GOOD_TECHNICAL_ANSWER + " Updated.")
    assert second.json()["input_mode"] == "text"

    client.post(_url(interview, question, "/evaluation"), headers=user_a)
    locked = client.put(url, headers=user_a, json={"answer_text": GOOD_TECHNICAL_ANSWER})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "ANSWER_ALREADY_EVALUATED"


# --- evaluations ---------------------------------------------------------------------------------


def test_evaluation_is_persisted_and_idempotent(client, user_a, cv_id):
    interview = create_interview(client, user_a, cv_id).json()
    question = interview["questions"][0]
    url = _url(interview, question, "/evaluation")

    assert client.post(url, headers=user_a).json()["error"]["code"] == "ANSWER_NOT_FOUND"
    assert client.get(url, headers=user_a).json()["error"]["code"] == "EVALUATION_NOT_FOUND"
    client.put(_url(interview, question, "/answer"), headers=user_a, json={"answer_text": GOOD_TECHNICAL_ANSWER})

    created = client.post(url, headers=user_a)
    repeated = client.post(url, headers=user_a)
    fetched = client.get(url, headers=user_a)

    assert (created.status_code, repeated.status_code, fetched.status_code) == (201, 200, 200)
    assert created.json() == repeated.json() == fetched.json()
    body = created.json()
    assert set(body["category_scores"]) == {"relevance", "clarity", "technical_depth", "structure"}
    assert "confidence" not in created.text.lower()
    assert all(0 <= v <= 100 for v in [body["overall_score"], *body["category_scores"].values()])
    assert 1 <= len(body["strengths"]) <= 3 and 1 <= len(body["weaknesses"]) <= 3
    assert body["improvement_tip"] and body["ideal_answer"]
    assert body["feedback_source"] == "rules"
    assert body["scoring_version"] == "lexical-v2"
    assert created.json()["created_at"].endswith("Z")


def test_resume_state_tracks_progress(client, user_a, cv_id):
    interview = create_interview(client, user_a, cv_id).json()
    answer_and_evaluate(client, user_a, interview["id"], interview["questions"][0]["id"])
    client.put(_url(interview, interview["questions"][1], "/answer"), headers=user_a, json={"answer_text": GOOD_TECHNICAL_ANSWER})

    state = client.get(_url(interview), headers=user_a).json()

    assert state["progress"] == {"answered": 2, "evaluated": 1, "total": 5}
    assert state["current_position"] == 2
    assert [q["state"] for q in state["questions"]][:3] == ["evaluated", "answered", "pending"]


# --- completion and results ----------------------------------------------------------------------


def test_complete_requires_every_question_evaluated(client, user_a, cv_id):
    interview = create_interview(client, user_a, cv_id).json()
    answer_and_evaluate(client, user_a, interview["id"], interview["questions"][0]["id"])

    response = client.post(_url(interview, tail="/complete"), headers=user_a)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INTERVIEW_INCOMPLETE"
    assert error["details"][0]["positions"] == [2, 3, 4, 5]
    assert client.get(_url(interview, tail="/results"), headers=user_a).json()["error"]["code"] == "RESULTS_NOT_AVAILABLE"


def test_results_follow_the_documented_formulas(client, user_a):
    _, interview, results = full_interview(client, user_a)

    evaluations = [item["evaluation"] for item in results["items"]]

    def mean(values):
        return int(sum(values) / len(values) + 0.5)

    assert results["interview"]["overall_score"] == mean([e["overall_score"] for e in evaluations])
    for key in ("structure", "relevance", "clarity", "technical_depth"):
        assert results["breakdown"][key] == mean([e["category_scores"][key] for e in evaluations])
    b = results["breakdown"]
    assert b["communication"] == int((b["clarity"] + b["structure"]) / 2 + 0.5)
    assert len(results["recommendations"]) == 3
    assert results["additional_strength"] and results["additional_improvement"]
    assert results["generated_by"] == "rules"
    assert [item["position"] for item in results["items"]] == [1, 2, 3, 4, 5]
    assert results["items"][0]["answer_text"] == GOOD_TECHNICAL_ANSWER
    assert results["interview"]["status"] == "completed"
    assert results["interview"]["completed_at"].endswith("Z")
    # Completing again returns the stored results unchanged.
    again = client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=user_a)
    assert again.status_code == 200 and again.json() == results
    assert client.get(f"/api/v1/interviews/{interview['id']}/results", headers=user_a).json() == results


def test_client_supplied_scores_are_ignored(client, user_a, cv_id):
    """S-03: the old frontend sent its own scores; the server must ignore any such payload."""
    interview = create_interview(client, user_a, cv_id).json()
    for question in interview["questions"]:
        answer_and_evaluate(client, user_a, interview["id"], question["id"])

    response = client.post(
        _url(interview, tail="/complete"), headers=user_a,
        json={"items": [{"ev": {"score": 100}}], "overall_score": 100, "breakdown": {"relevance": 100}},
    )

    assert response.status_code == 200
    body = response.json()
    stored = [item["evaluation"]["overall_score"] for item in body["items"]]
    assert body["interview"]["overall_score"] == int(sum(stored) / len(stored) + 0.5)
    assert body["breakdown"]["relevance"] == int(
        sum(i["evaluation"]["category_scores"]["relevance"] for i in body["items"]) / len(stored) + 0.5
    )


def test_abandon_blocks_further_answers_and_is_excluded(client, user_a, cv_id):
    interview = create_interview(client, user_a, cv_id).json()

    first = client.post(_url(interview, tail="/abandon"), headers=user_a)
    repeat = client.post(_url(interview, tail="/abandon"), headers=user_a)
    answer = client.put(_url(interview, interview["questions"][0], "/answer"), headers=user_a,
                        json={"answer_text": GOOD_TECHNICAL_ANSWER})

    assert first.json() == {"id": interview["id"], "status": "abandoned"} == repeat.json()
    assert answer.status_code == 409 and answer.json()["error"]["code"] == "INTERVIEW_NOT_ACTIVE"
    assert client.post(_url(interview, tail="/complete"), headers=user_a).status_code == 409
    assert client.get("/api/v1/interviews", headers=user_a).json()["total"] == 0


def test_completed_interview_cannot_be_abandoned(client, user_a):
    _, interview, _ = full_interview(client, user_a)
    response = client.post(f"/api/v1/interviews/{interview['id']}/abandon", headers=user_a)
    assert response.status_code == 409


# --- history and performance ----------------------------------------------------------------------


def test_new_user_has_empty_history_and_stats(client, user_a):
    assert client.get("/api/v1/interviews", headers=user_a).json()["items"] == []
    assert client.get("/api/v1/performance/skills", headers=user_a).json() == {"skills": [], "interviews_counted": 0}
    assert client.get("/api/v1/performance/summary", headers=user_a).json() == {
        "interviews_completed": 0, "average_score": None,
        "strongest_skill": None, "weakest_skill": None, "trend": [],
    }


def test_history_skills_and_summary_reflect_completed_interviews(client, user_a):
    _, first, r1 = full_interview(client, user_a, interview_type="technical")
    _, second, r2 = full_interview(client, user_a, interview_type="behavioral", target_role="Data Analyst")

    history = client.get("/api/v1/interviews", headers=user_a).json()
    assert history["total"] == 2
    assert [h["id"] for h in history["items"]] == [second["id"], first["id"]]  # newest first
    assert set(history["items"][0]) == {"id", "completed_at", "target_role", "interview_type", "difficulty",
                                        "question_count", "overall_score", "status"}
    filtered = client.get("/api/v1/interviews?type=technical", headers=user_a).json()
    assert [h["id"] for h in filtered["items"]] == [first["id"]]
    assert client.get("/api/v1/interviews?status=abandoned", headers=user_a).status_code == 422

    skills = client.get("/api/v1/performance/skills", headers=user_a).json()
    assert skills["interviews_counted"] == 2
    assert [s["key"] for s in skills["skills"]] and len(skills["skills"]) == 5
    scores = [s["score"] for s in skills["skills"]]
    assert scores == sorted(scores, reverse=True)
    for skill in skills["skills"]:
        expected = int((r1["breakdown"][skill["key"]] + r2["breakdown"][skill["key"]]) / 2 + 0.5)
        assert skill["score"] == expected

    summary = client.get("/api/v1/performance/summary", headers=user_a).json()
    assert summary["interviews_completed"] == 2
    overall = [r1["interview"]["overall_score"], r2["interview"]["overall_score"]]
    assert summary["average_score"] == int(sum(overall) / 2 + 0.5)
    assert [t["interview_id"] for t in summary["trend"]] == [first["id"], second["id"]]  # oldest first
    assert summary["strongest_skill"] == skills["skills"][0]
    assert summary["weakest_skill"] == skills["skills"][-1]
