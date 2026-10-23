"""Helpers that drive the API like the frontend does."""

from tests.factories import GOOD_TECHNICAL_ANSWER, make_pdf


def upload_cv(client, headers, filename="cv.pdf", data=None, content_type="application/pdf"):
    return client.post("/api/v1/cvs", headers=headers, files={"file": (filename, data or make_pdf(), content_type)})


def create_interview(client, headers, cv_id, **overrides):
    body = {
        "cv_id": cv_id,
        "target_role": "AI Engineer",
        "interview_type": "technical",
        "difficulty": "intermediate",
        "question_count": 5,
    } | overrides
    return client.post("/api/v1/interviews", headers=headers, json=body)


def answer_and_evaluate(client, headers, interview_id, question_id, text=GOOD_TECHNICAL_ANSWER):
    answer = client.put(
        f"/api/v1/interviews/{interview_id}/questions/{question_id}/answer", headers=headers, json={"answer_text": text}
    )
    assert answer.status_code in (200, 201), answer.text
    evaluation = client.post(f"/api/v1/interviews/{interview_id}/questions/{question_id}/evaluation", headers=headers)
    assert evaluation.status_code in (200, 201), evaluation.text
    return evaluation.json()


def full_interview(client, headers, **overrides):
    """Upload a CV, run a whole interview and complete it. Returns (cv, interview, results)."""
    cv = upload_cv(client, headers).json()["cv"]
    interview = create_interview(client, headers, cv["id"], **overrides).json()
    for question in interview["questions"]:
        answer_and_evaluate(client, headers, interview["id"], question["id"])
    results = client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=headers)
    assert results.status_code == 200, results.text
    return cv, interview, results.json()
