"""Users can only ever reach their own data (spec S-02).

User B tries every user-specific endpoint with user A's ids. Every attempt
must fail with 404 (not 403), so B cannot even learn that the ids exist,
and A's data must be unchanged afterwards.
"""

import pytest

from tests.factories import GOOD_TECHNICAL_ANSWER
from tests.helpers import create_interview, full_interview, upload_cv


@pytest.fixture
def a_data(client, user_a):
    cv, completed, _ = full_interview(client, user_a)
    # A second, still running interview with one answered question.
    running = create_interview(client, user_a, cv["id"]).json()
    question = running["questions"][0]
    client.put(f"/api/v1/interviews/{running['id']}/questions/{question['id']}/answer",
               headers=user_a, json={"answer_text": GOOD_TECHNICAL_ANSWER})
    return {"cv": cv, "completed": completed, "running": running, "question": question}


def _requests(a):
    cv_id = a["cv"]["id"]
    done = a["completed"]
    run = a["running"]
    q_done = done["questions"][0]["id"]
    q_run = a["question"]["id"]
    return [
        ("GET", f"/api/v1/cvs/{cv_id}", None, "CV_NOT_FOUND"),
        ("DELETE", f"/api/v1/cvs/{cv_id}", None, "CV_NOT_FOUND"),
        ("GET", f"/api/v1/interviews/{done['id']}", None, "INTERVIEW_NOT_FOUND"),
        ("GET", f"/api/v1/interviews/{done['id']}/results", None, "INTERVIEW_NOT_FOUND"),
        ("POST", f"/api/v1/interviews/{done['id']}/complete", None, "INTERVIEW_NOT_FOUND"),
        ("GET", f"/api/v1/interviews/{done['id']}/questions/{q_done}/evaluation", None, "INTERVIEW_NOT_FOUND"),
        ("POST", f"/api/v1/interviews/{run['id']}/questions/{q_run}/evaluation", None, "INTERVIEW_NOT_FOUND"),
        ("PUT", f"/api/v1/interviews/{run['id']}/questions/{q_run}/answer",
         {"answer_text": "I am user B overwriting user A's answer, which must not work."}, "INTERVIEW_NOT_FOUND"),
        ("POST", f"/api/v1/interviews/{run['id']}/abandon", None, "INTERVIEW_NOT_FOUND"),
        ("POST", "/api/v1/interviews",
         {"cv_id": cv_id, "target_role": "AI Engineer", "interview_type": "technical",
          "difficulty": "beginner", "question_count": 5}, "CV_NOT_FOUND"),
    ]


def test_other_user_gets_404_for_every_foreign_resource(client, user_a, user_b, a_data):
    for method, path, body, code in _requests(a_data):
        response = client.request(method, path, headers=user_b, json=body)
        assert response.status_code == 404, (method, path, response.text)
        assert response.json()["error"]["code"] == code, (method, path)
        # Nothing about A's data leaks into the error.
        assert a_data["cv"]["original_filename"] not in response.text


def test_owner_still_has_full_access_after_attacks(client, user_a, user_b, a_data):
    for method, path, body, _ in _requests(a_data):
        client.request(method, path, headers=user_b, json=body)

    assert client.get(f"/api/v1/cvs/{a_data['cv']['id']}", headers=user_a).status_code == 200
    results = client.get(f"/api/v1/interviews/{a_data['completed']['id']}/results", headers=user_a)
    assert results.status_code == 200
    state = client.get(f"/api/v1/interviews/{a_data['running']['id']}", headers=user_a).json()
    assert state["status"] == "in_progress"
    assert state["progress"]["answered"] == 1


def test_question_id_from_another_interview_is_rejected(client, user_a, a_data):
    """Mixing a valid interview id with a question id from a different interview fails."""
    foreign_question = a_data["completed"]["questions"][1]["id"]
    response = client.put(
        f"/api/v1/interviews/{a_data['running']['id']}/questions/{foreign_question}/answer",
        headers=user_a, json={"answer_text": GOOD_TECHNICAL_ANSWER},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUESTION_NOT_FOUND"


def test_lists_and_statistics_only_contain_own_data(client, user_a, user_b, a_data):
    upload_cv(client, user_b)

    b_cvs = client.get("/api/v1/cvs", headers=user_b).json()
    b_history = client.get("/api/v1/interviews", headers=user_b).json()
    b_skills = client.get("/api/v1/performance/skills", headers=user_b).json()
    b_summary = client.get("/api/v1/performance/summary", headers=user_b).json()

    assert b_cvs["total"] == 1 and b_cvs["items"][0]["id"] != a_data["cv"]["id"]
    assert b_history == {"items": [], "total": 0, "limit": 50, "offset": 0}
    assert b_skills == {"skills": [], "interviews_counted": 0}
    assert b_summary["interviews_completed"] == 0 and b_summary["average_score"] is None
    assert client.get("/api/v1/interviews", headers=user_a).json()["total"] == 1


def test_clearing_my_data_never_touches_other_users(client, user_a, user_b, a_data):
    full_interview(client, user_b)

    response = client.delete("/api/v1/users/me/data", headers=user_b)

    assert response.status_code == 200
    assert response.json() == {"reset": True, "deleted": {"cvs": 1, "interviews": 1}}
    assert client.get("/api/v1/interviews", headers=user_b).json()["total"] == 0
    assert client.get("/api/v1/interviews", headers=user_a).json()["total"] == 1
    assert client.get("/api/v1/cvs", headers=user_a).json()["total"] == 1
