"""E11-E19: interviews, answers, evaluations, results and history."""

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.presenters import (
    answer_out,
    evaluation_out,
    interview_created_out,
    interview_state_out,
    plan_out,
    results_out,
    summary_out,
)
from app.core.errors import AppError
from app.db.session import get_db
from app.models import User
from app.models.enums import InterviewType, SessionStatus
from app.schemas.interviews import (
    AnswerIn,
    AnswerOut,
    EvaluationOut,
    HistoryPage,
    InterviewCreatedOut,
    InterviewCreateIn,
    InterviewStateOut,
    ResultsOut,
    StatusOut,
)
from app.schemas.intelligence import ImprovementPlanOut
from app.services import improvement_service, intelligence_service
from app.services import interview_service as svc

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", response_model=InterviewCreatedOut, status_code=status.HTTP_201_CREATED)
def create_interview(body: InterviewCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create an interview and select all of its questions from the curated bank."""
    session = svc.create_interview(
        db, user,
        cv_id=body.cv_id,
        target_role=body.target_role,
        interview_type=body.interview_type,
        difficulty=body.difficulty,
        question_count=body.question_count,
        job_description=(body.job_description or "").strip() or None,
        adaptive_mode=body.adaptive,
    )
    return interview_created_out(session)


@router.get("", response_model=HistoryPage)
def list_interviews(
    status_filter: str = Query("completed", alias="status"),
    type_filter: InterviewType | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The signed-in user's completed interviews, newest first."""
    if status_filter != SessionStatus.COMPLETED.value:
        raise AppError("VALIDATION_ERROR", "Only status=completed is supported.", 422,
                       details=[{"field": "status", "issue": "unsupported"}])
    items, total = svc.history(db, user, interview_type=type_filter, limit=limit, offset=offset)
    return HistoryPage(items=[summary_out(s) for s in items], total=total, limit=limit, offset=offset)


@router.get("/{interview_id}", response_model=InterviewStateOut)
def get_interview(interview_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current state of one interview (used to resume after a page reload)."""
    return interview_state_out(svc.get_owned_interview(db, user, interview_id))


@router.post("/{interview_id}/abandon", response_model=StatusOut)
def abandon_interview(interview_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = svc.abandon(db, user, interview_id)
    return StatusOut(id=session.id, status=session.status.value)


@router.post("/{interview_id}/complete", response_model=ResultsOut)
def complete_interview(interview_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Aggregate the stored evaluations into results. Takes no body: scores sent
    by a client are never trusted (spec S-03)."""
    session = svc.complete(db, user, interview_id)
    return results_out(session, intelligence_service.decisions_by_question(db, session.id))


@router.put("/{interview_id}/questions/{question_id}/answer", response_model=AnswerOut,
            responses={201: {"model": AnswerOut, "description": "Answer created"}})
def submit_answer(
    interview_id: uuid.UUID,
    question_id: uuid.UUID,
    body: AnswerIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session, answer, created = svc.submit_answer(db, user, interview_id, question_id, body.answer_text)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return answer_out(session, answer)


@router.post("/{interview_id}/questions/{question_id}/evaluation", response_model=EvaluationOut,
             responses={201: {"model": EvaluationOut, "description": "Evaluation created"}})
def evaluate_answer(
    interview_id: uuid.UUID,
    question_id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Score the stored answer (idempotent: a repeat call returns the stored evaluation).

    In adaptive interviews the response may include `follow_up` (a question inserted
    right after this one) and `replaced_question` (a later question adjusted in difficulty).
    """
    evaluation, created, adaptation = svc.evaluate(db, user, interview_id, question_id)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    session = svc.get_owned_interview(db, user, interview_id)
    return evaluation_out(evaluation, question_id, svc.get_question(session, question_id), adaptation)


@router.get("/{interview_id}/questions/{question_id}/evaluation", response_model=EvaluationOut)
def get_evaluation(
    interview_id: uuid.UUID, question_id: uuid.UUID,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    evaluation = svc.get_evaluation(db, user, interview_id, question_id)
    session = svc.get_owned_interview(db, user, interview_id)
    question = svc.get_question(session, question_id)
    return evaluation_out(evaluation, question_id, question, svc._existing_adaptation(session, question, db))


@router.get("/{interview_id}/results", response_model=ResultsOut)
def get_results(interview_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = svc.get_owned_interview(db, user, interview_id)
    if session.status is not SessionStatus.COMPLETED or not session.breakdown:
        raise AppError("RESULTS_NOT_AVAILABLE", "Results are available once the interview is finished.", 409)
    return results_out(session, intelligence_service.decisions_by_question(db, session.id))


@router.get("/{interview_id}/improvement-plan", response_model=ImprovementPlanOut)
def get_improvement_plan(interview_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Personalised improvement plan for a completed interview."""
    return plan_out(improvement_service.get_plan(db, user, interview_id))
