"""Shared intelligence service (Milestone 5): assembles context for retrieval,
evaluation, the interview agent and coaching from the database, so the routes
and the lifecycle code never touch model logic directly.

Coordinated workflow (one competency vocabulary, see intelligence/competencies.py):
  1. plan:     earlier questions + competency evidence -> select_questions(history, ledger)
  2. evaluate: the question's own rubric, misconceptions and reference -> evaluator (+ optional LLM review)
  3. adapt:    evaluation evidence + interview state -> agent decision (validated by policy)
  4. coach:    evidence across interviews -> improvement plan (improvement_service)
  5. the next plan reads the updated evidence (step 1)
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.agent import MINUTES_PER_QUESTION_BUDGET, AgentContext
from app.intelligence.competencies import CompetencyLedger, build_ledger
from app.models import AgentDecisionRecord, InterviewQuestion, InterviewSession, User
from app.models.enums import SessionStatus


def candidate_evidence(db: Session, user: User, profile=None) -> tuple[list[str], CompetencyLedger]:
    """Question texts from the user's earlier interviews (newest first) and their competency ledger."""
    from app.services.improvement_service import _completed_sessions, _evidence

    completed = _completed_sessions(db, user)  # oldest first, already filtered by user
    answers = [e for s in completed for e in _evidence(s)]
    history = [q.text for s in reversed(completed) for q in s.questions]
    # Unfinished interviews of this user also count as "seen", after the completed ones.
    others = db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id,
                                                       InterviewSession.status != SessionStatus.COMPLETED)
                        .order_by(InterviewSession.created_at.desc()).limit(5))
    history += [q.text for s in others for q in s.questions]
    return history, build_ledger(profile, answers)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def agent_context(db: Session, session: InterviewSession, question: InterviewQuestion, evaluation) -> AgentContext:
    """Everything the agent may consider for one evaluated answer (no CV text)."""
    decisions = list(db.scalars(select(AgentDecisionRecord).where(AgentDecisionRecord.session_id == session.id)))
    by_question = {q.id: q for q in session.questions}
    probed = {d.target_concept for d in decisions if d.target_concept and d.kind == "follow_up" and d.result_question_id}
    deepened, per_competency = set(), {}
    for d in decisions:
        if d.kind != "follow_up" or not d.result_question_id:
            continue
        parent = by_question.get(d.question_id)
        competency = ((parent.focus_skills or ["this topic"])[0]) if parent else "this topic"
        per_competency[competency] = per_competency.get(competency, 0) + 1
        if d.action == "deepen":
            deepened.add(competency)
    demonstrated_in_session = set()
    for q in session.questions:
        ev = q.answer.evaluation if q.answer else None
        if ev is not None and ev.id != evaluation.id:
            demonstrated_in_session |= {c["concept"] for c in (ev.concept_evidence or [])
                                        if c.get("status") in ("demonstrated", "partial")}
    created = _as_utc(session.created_at) or datetime.now(UTC)
    elapsed = (datetime.now(UTC) - created).total_seconds() / 60
    dims = {d["key"]: d.get("score") for d in (evaluation.dimensions or [])}
    unanswered = sum(1 for q in session.questions if q.answer is None)
    return AgentContext(
        question_text=question.text,
        question_type=question.question_type,
        category=question.category,
        key_points=list(question.key_points or []),
        focus_skills=list(question.focus_skills or []),
        target_role=session.target_role,
        interview_type=session.interview_type.value,
        adaptive=bool(session.adaptive),
        reference=question.ideal_answer,
        overall=evaluation.score,
        dimensions=dims,
        demonstrated=[c["concept"] for c in (evaluation.concept_evidence or []) if c.get("status") in ("demonstrated", "partial")],
        missing=list(evaluation.missing_concepts or []),
        incorrect_claims=list(evaluation.incorrect_claims or []),
        unsupported_claims=list(evaluation.unsupported_claims or []),
        evidence_level=evaluation.evidence_level or "sufficient",
        answer_excerpt=question.answer.answer_text if question.answer else "",
        follow_ups_used=sum(1 for q in session.questions if q.category == "follow_up"),
        follow_up_limit=session.max_follow_ups or 0,
        has_follow_up=any(q.parent_question_id == question.id for q in session.questions),
        is_follow_up=question.category == "follow_up",
        probed_concepts=probed,
        deepened_competencies=deepened,
        follow_ups_per_competency=per_competency,
        demonstrated_in_session=demonstrated_in_session,
        asked_texts={q.text.lower() for q in session.questions},
        questions_remaining=unanswered,
        elapsed_minutes=elapsed,
        time_budget_minutes=float(session.question_count * MINUTES_PER_QUESTION_BUDGET),
    )


def decisions_by_question(db: Session, session_id) -> dict:
    rows = db.scalars(select(AgentDecisionRecord).where(AgentDecisionRecord.session_id == session_id,
                                                        AgentDecisionRecord.kind == "follow_up"))
    return {r.question_id: r for r in rows}


def decision_for(db: Session, question_id, kind: str = "follow_up") -> AgentDecisionRecord | None:
    return db.scalar(select(AgentDecisionRecord).where(AgentDecisionRecord.question_id == question_id,
                                                       AgentDecisionRecord.kind == kind))
