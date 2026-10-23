"""Generate, store and read improvement plans (Milestone 4, feature 5)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.intelligence.improvement import AnswerEvidence, build_plan
from app.models import Answer, ImprovementPlan, InterviewQuestion, InterviewSession, QuestionBankItem, User
from app.models.enums import QuestionKind, SessionStatus
from app.services import profile_service
from app.services.question_selection import build_context

_LEGACY_DIMENSIONS = {"relevance": "relevance_score", "structure": "structure_score", "communication": "clarity_score"}


def _evidence(session: InterviewSession) -> list[AnswerEvidence]:
    items = []
    by_id = {q.id: q for q in session.questions}
    for q in session.questions:
        ev = q.answer.evaluation if q.answer else None
        if ev is None:
            continue
        if ev.dimensions:
            dims = {d["key"]: d.get("score") for d in ev.dimensions}
        else:  # evaluations stored before Milestone 4
            dims = {key: getattr(ev, attr) for key, attr in _LEGACY_DIMENSIONS.items()}
        parent = by_id.get(q.parent_question_id) if q.parent_question_id else None
        parent_is_project = parent is not None and parent.category == "project"
        items.append(AnswerEvidence(
            interview_id=str(session.id),
            question_text=q.text,
            question_type=q.question_type.value,
            category=q.category,
            focus_skills=[] if parent_is_project else list(q.focus_skills or []),
            overall=ev.score,
            dimensions=dims,
            evidence_level=ev.evidence_level or "sufficient",
            group=str(q.parent_question_id or q.id),
        ))
    return items


def _completed_sessions(db: Session, user: User):
    return list(db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id, InterviewSession.status == SessionStatus.COMPLETED)
        .order_by(InterviewSession.completed_at)
        .options(selectinload(InterviewSession.questions).selectinload(InterviewQuestion.answer).selectinload(Answer.evaluation))
    ))


def generate_for_session(db: Session, user: User, session: InterviewSession) -> ImprovementPlan:
    if session.status is not SessionStatus.COMPLETED:
        raise AppError("RESULTS_NOT_AVAILABLE", "The plan is available once the interview is finished.", 409)
    profile = profile_service.confirmed_profile(db, user)
    ctx = build_context(target_role=session.target_role, cv_skills=[], profile=profile,
                        job_description=session.job_description)

    earlier = [s for s in _completed_sessions(db, user) if s.id != session.id and s.completed_at <= session.completed_at]
    history = [e for s in earlier for e in _evidence(s)]
    previous = earlier[-1] if earlier else None
    previous_plan = None
    if previous is not None:
        stored = db.scalar(select(ImprovementPlan).where(ImprovementPlan.interview_id == previous.id))
        previous_plan = stored.data if stored else None

    asked = {q.text.lower() for s in [*earlier, session] for q in s.questions}
    practice_pool = [
        {"bank_question_id": str(b.id), "text": b.text, "type": b.question_type.value, "skill_tags": list(b.skill_tags or [])}
        for b in db.scalars(select(QuestionBankItem).where(QuestionBankItem.is_active.is_(True)).order_by(QuestionBankItem.text))
        if b.kind is QuestionKind.GENERIC and b.text.lower() not in asked
    ]
    data = build_plan(
        interview_id=str(session.id),
        target_role=session.target_role,
        required_skills=ctx.required,
        job_skills=ctx.job_skills,
        profile_skills=[s.name for s in profile.technical_skills] if profile else [],
        current=_evidence(session),
        history=history,
        previous_plan=previous_plan,
        previous_overall=previous.overall_score if previous else None,
        current_overall=session.overall_score or 0,
        practice_pool=practice_pool,
    )
    data["personalized"] = profile is not None
    plan = db.scalar(select(ImprovementPlan).where(ImprovementPlan.interview_id == session.id))
    if plan is None:
        plan = ImprovementPlan(user_id=user.id, interview_id=session.id)
        db.add(plan)
    plan.target_role = session.target_role[:100]
    plan.plan_version = data["version"]
    plan.data = data
    db.commit()
    db.refresh(plan)
    return plan


def get_plan(db: Session, user: User, interview_id: uuid.UUID) -> ImprovementPlan:
    """The plan for one of the user's completed interviews (generated on first request if missing)."""
    from app.services.interview_service import get_owned_interview

    session = get_owned_interview(db, user, interview_id)  # 404 for other users' interviews
    plan = db.scalar(select(ImprovementPlan).where(ImprovementPlan.interview_id == session.id,
                                                   ImprovementPlan.user_id == user.id))
    return plan or generate_for_session(db, user, session)


def latest_plan(db: Session, user: User) -> ImprovementPlan:
    sessions = _completed_sessions(db, user)
    if not sessions:
        raise AppError("PLAN_NOT_FOUND", "Complete an interview to get your improvement plan.", 404)
    return get_plan(db, user, sessions[-1].id)
