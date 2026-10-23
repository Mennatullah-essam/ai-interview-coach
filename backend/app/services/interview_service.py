"""Interview lifecycle, answers, evaluations, results, history and performance.

Ownership rule (spec S-02): every lookup is filtered by the authenticated
user's id. A resource that belongs to someone else is reported exactly like a
missing one (404), so ids cannot be probed. No function accepts a user id or a
score from the client.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.models import CV, Answer, Evaluation, InterviewQuestion, InterviewSession, QuestionBankItem, User
from app.models.enums import Difficulty, InterviewType, SessionStatus
from app.intelligence import adaptive
from app.scoring import templates
from app.scoring.scorer import evaluate_answer
from app.scoring.similarity import EngineUnavailable, get_engine
from app.services import intelligence_service, profile_service
from app.services.question_selection import _role_ok, match_roles, round_half_up, select_questions

logger = logging.getLogger(__name__)

MIN_ANSWER_CHARS = 30
MAX_ANSWER_CHARS = 1500
CATEGORY_KEYS = ("relevance", "clarity", "technical_depth", "structure")


def _now() -> datetime:
    return datetime.now(UTC)


# --- errors ------------------------------------------------------------------------


def _err(code: str, message: str, status: int, **kw) -> AppError:
    return AppError(code, message, status, **kw)


CV_NOT_FOUND = lambda: _err("CV_NOT_FOUND", "CV not found.", 404)  # noqa: E731
INTERVIEW_NOT_FOUND = lambda: _err("INTERVIEW_NOT_FOUND", "Interview not found.", 404)  # noqa: E731
QUESTION_NOT_FOUND = lambda: _err("QUESTION_NOT_FOUND", "Question not found in this interview.", 404)  # noqa: E731


def _not_active() -> AppError:
    return _err("INTERVIEW_NOT_ACTIVE", "This interview has already been finished or exited.", 409)


# --- ownership-checked lookups ------------------------------------------------------------------


def get_owned_cv(db: Session, user: User, cv_id: uuid.UUID) -> CV:
    cv = db.scalar(select(CV).where(CV.id == cv_id, CV.user_id == user.id))
    if cv is None:
        raise CV_NOT_FOUND()
    return cv


def get_owned_interview(db: Session, user: User, interview_id: uuid.UUID) -> InterviewSession:
    session = db.scalar(
        select(InterviewSession)
        .where(InterviewSession.id == interview_id, InterviewSession.user_id == user.id)
        .options(selectinload(InterviewSession.questions).selectinload(InterviewQuestion.answer).selectinload(Answer.evaluation))
    )
    if session is None:
        raise INTERVIEW_NOT_FOUND()
    return session


def get_question(session: InterviewSession, question_id: uuid.UUID) -> InterviewQuestion:
    for question in session.questions:
        if question.id == question_id:
            return question
    raise QUESTION_NOT_FOUND()


# --- create ------------------------------------------------------------------------------------


def create_interview(
    db: Session,
    user: User,
    *,
    cv_id: uuid.UUID | None,
    target_role: str,
    interview_type: InterviewType,
    difficulty: Difficulty,
    question_count: int,
    job_description: str | None = None,
    adaptive_mode: bool = False,
) -> InterviewSession:
    if cv_id is None:
        raise _err("CV_REQUIRED", "Please upload your CV first.", 422)
    cv = get_owned_cv(db, user, cv_id)

    interview_id = uuid.uuid4()
    bank = list(db.scalars(select(QuestionBankItem).where(QuestionBankItem.is_active.is_(True))))
    # Only a profile the candidate reviewed and confirmed personalises the plan.
    profile = profile_service.confirmed_profile(db, user)
    # Milestone 5: earlier questions and competency evidence steer retrieval (less repetition,
    # more coverage of required skills that are unassessed or weak).
    history_texts, ledger = intelligence_service.candidate_evidence(db, user, profile)
    selected = select_questions(
        bank,
        target_role=target_role,
        interview_type=interview_type,
        difficulty=difficulty,
        question_count=question_count,
        cv_skills=list(cv.skills or []),
        seed=str(interview_id),
        profile=profile,
        job_description=job_description,
        history=history_texts,
        ledger=ledger,
    )
    session = InterviewSession(
        id=interview_id,
        user_id=user.id,
        cv_id=cv.id,
        target_role=target_role,
        interview_type=interview_type,
        difficulty=difficulty,
        question_count=question_count,
        status=SessionStatus.IN_PROGRESS,
        adaptive=adaptive_mode,
        max_follow_ups=adaptive.max_follow_ups(question_count) if adaptive_mode else 0,
        personalized=profile is not None,
        job_description=job_description,
    )
    session.questions = [
        InterviewQuestion(
            position=i,
            text=q.text,
            question_type=q.question_type,
            ideal_answer=q.ideal_answer,
            key_points=q.key_points,
            misconceptions=q.misconceptions,
            bank_question_id=q.bank_question_id,
            category=q.category,
            selection_reason=q.reason,
            focus_skills=q.focus_skills,
        )
        for i, q in enumerate(selected, start=1)
    ]
    db.add(session)
    db.commit()
    return get_owned_interview(db, user, interview_id)


# --- answers -----------------------------------------------------------------------------------


def validate_answer_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise _err("ANSWER_EMPTY", "Please write an answer before submitting.", 422,
                   details=[{"field": "answer_text", "issue": "empty"}])
    if len(text) < MIN_ANSWER_CHARS:
        raise _err("ANSWER_TOO_SHORT", f"Please write at least {MIN_ANSWER_CHARS} characters so your answer can be evaluated.",
                   422, details=[{"field": "answer_text", "issue": "min_length", "limit": MIN_ANSWER_CHARS}])
    if len(text) > MAX_ANSWER_CHARS:
        raise _err("ANSWER_TOO_LONG", f"Answers can be at most {MAX_ANSWER_CHARS} characters.", 422,
                   details=[{"field": "answer_text", "issue": "max_length", "limit": MAX_ANSWER_CHARS}])
    return text


def submit_answer(db: Session, user: User, interview_id: uuid.UUID, question_id: uuid.UUID, raw_text: str):
    session = get_owned_interview(db, user, interview_id)
    question = get_question(session, question_id)
    text = validate_answer_text(raw_text)
    if session.status is not SessionStatus.IN_PROGRESS:
        raise _not_active()
    answer = question.answer
    if answer is not None and answer.evaluation is not None:
        raise _err("ANSWER_ALREADY_EVALUATED", "This answer has already been evaluated and can't be changed.", 409)
    created = answer is None
    if created:
        answer = Answer(question_id=question.id, answer_text=text)
        db.add(answer)
    else:
        answer.answer_text = text
    try:
        db.commit()
    except IntegrityError:  # a concurrent submit created it first
        db.rollback()
        answer = db.scalar(select(Answer).where(Answer.question_id == question.id))
        created = False
    db.refresh(answer)
    return session, answer, created


# --- evaluations ----------------------------------------------------------------------------------


def evaluate(db: Session, user: User, interview_id: uuid.UUID, question_id: uuid.UUID):
    session = get_owned_interview(db, user, interview_id)
    question = get_question(session, question_id)
    answer = question.answer
    if answer is None:
        raise _err("ANSWER_NOT_FOUND", "Submit an answer before requesting its evaluation.", 404)
    if answer.evaluation is not None:  # idempotent: same evaluation and same adaptation
        return answer.evaluation, False, _existing_adaptation(session, question, db)
    if session.status is not SessionStatus.IN_PROGRESS:
        raise _not_active()

    try:
        engine = get_engine()
    except EngineUnavailable as exc:
        raise _err("AI_SERVICE_UNAVAILABLE", "The evaluation service is temporarily unavailable. Please try again.",
                   503, retryable=True) from exc

    cv_skills = []
    if session.cv_id is not None:
        cv = db.get(CV, session.cv_id)
        cv_skills = list(cv.skills or []) if cv else []
    result = evaluate_answer(
        engine,
        question=question.text,
        question_type=question.question_type,
        answer=answer.answer_text,
        reference=question.ideal_answer or "",
        key_points=list(question.key_points or []),
        extra_terms=cv_skills,
        misconceptions=list(question.misconceptions or []),
        category=question.category,
    )
    _llm_review(result, question, answer.answer_text)
    evaluation = Evaluation(
        answer_id=answer.id,
        score=result.overall_score,
        relevance_score=result.relevance,
        clarity_score=result.clarity,
        technical_depth_score=result.technical_depth,
        structure_score=result.structure,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        improvement_tip=result.improvement_tip,
        ideal_answer=question.ideal_answer,
        feedback_source=result.feedback_source,
        scoring_version=result.scoring_version,
        model_info=result.model_info,
        semantic_similarity=result.semantic_similarity,
        latency_ms=result.latency_ms,
        dimensions=[d.as_dict() for d in result.dimensions],
        missing_concepts=result.missing_concepts,
        suggestions=result.suggestions,
        explanation=result.explanation,
        concept_evidence=result.concept_evidence,
        unsupported_claims=result.unsupported_claims,
        incorrect_claims=result.incorrect_claims,
        evidence_level=result.evidence_level,
    )
    db.add(evaluation)
    try:
        db.commit()
    except IntegrityError:  # concurrent duplicate request: return the stored one
        db.rollback()
        stored = db.scalar(select(Evaluation).where(Evaluation.answer_id == answer.id))
        return stored, False, _existing_adaptation(get_owned_interview(db, user, interview_id), question, db)
    db.refresh(evaluation)
    logger.info("Evaluated answer %s in %d ms (%s)", answer.id, result.latency_ms, result.scoring_version)
    adaptation = {"follow_up": None, "replaced": None, "decision": None}
    if session.adaptive:
        adaptation = _adapt(db, user, session, question, evaluation)
    return evaluation, True, adaptation


def _llm_review(result, question: InterviewQuestion, answer_text: str) -> None:
    """Optional bounded LLM review of the rule-based result (no-op unless configured)."""
    from app.intelligence.evaluation_review import EvaluationReview, _SYSTEM, apply_review, review_prompt
    from app.llm.gateway import get_llm
    from app.scoring.scorer import recompute_totals

    gateway = get_llm()
    if not gateway.enabled_for("evaluation") or not question.key_points:
        return
    call = gateway.call("evaluation", _SYSTEM,
                        review_prompt(question.text, question.question_type.value, list(question.key_points or []),
                                      list(question.misconceptions or []), answer_text),
                        EvaluationReview, max_tokens=700)
    result.model_info["llm_review"] = {"status": call.reason, "model": call.model, "latency_ms": call.latency_ms}
    if call.value is None:
        return
    applied = apply_review(result, call.value, answer=answer_text, key_points=list(question.key_points or []),
                           keyword_list=bool(result.model_info.get("signals", {}).get("keyword_list")))
    recompute_totals(result, question.question_type)
    result.model_info["llm_review"]["applied"] = applied
    result.feedback_source = "hybrid"
    result.explanation += (" A language-model review adjusted key concepts and accuracy by at most 15 points; "
                           "every concept it credited is quoted from your answer.")


# --- adaptive interviews --------------------------------------------------------------------------


def _existing_adaptation(session: InterviewSession, question: InterviewQuestion, db: Session | None = None) -> dict:
    follow_up = next((q for q in session.questions if q.parent_question_id == question.id), None)
    decision = intelligence_service.decision_for(db, question.id) if db is not None else None
    return {"follow_up": follow_up, "replaced": None, "decision": decision}


def _adapt(db: Session, user: User, session: InterviewSession, question: InterviewQuestion, evaluation: Evaluation) -> dict:
    """Ask the hybrid agent what to do next and run its (policy-validated) decision.
    Fixed interviews never get here."""
    from app.intelligence.agent import decide
    from app.llm.gateway import get_llm
    from app.models import AgentDecisionRecord

    session = get_owned_interview(db, user, session.id)
    question = get_question(session, question.id)
    ctx = intelligence_service.agent_context(db, session, question, evaluation)
    decision = decide(ctx, get_llm())
    follow_up = None
    if decision.asks_follow_up:
        follow_up = _insert_after(db, session, question, decision)
    record = AgentDecisionRecord(
        session_id=session.id, question_id=question.id, kind="follow_up", action=decision.action,
        source=decision.source, policy=decision.policy[:40], llm_status=(decision.llm_status or None) and decision.llm_status[:40],
        rationale=decision.rationale, evidence=decision.evidence, target_concept=decision.target_concept,
        result_question_id=follow_up.id if follow_up is not None else None,
    )
    db.add(record)
    replaced = None
    if question.category != "follow_up":
        replaced = _adjust_next_question(db, session, question)
        if replaced is not None:
            db.add(AgentDecisionRecord(
                session_id=session.id, question_id=question.id, kind="difficulty", action="adjust_difficulty",
                source="rules", policy="accepted", rationale=replaced.selection_reason or "",
                evidence=[], result_question_id=replaced.id))
    db.commit()
    return {"follow_up": follow_up, "replaced": replaced, "decision": record}


def _insert_after(db: Session, session: InterviewSession, parent: InterviewQuestion, plan) -> InterviewQuestion:
    """Insert the follow-up right after its parent, shifting later positions by one."""
    later = sorted((q for q in session.questions if q.position > parent.position), key=lambda q: q.position)
    for q in later:  # two steps so the unique (session, position) rule never clashes
        q.position += 1000
    db.flush()
    for q in later:
        q.position -= 999
    db.flush()
    follow_up = InterviewQuestion(
        session_id=session.id,
        position=parent.position + 1,
        text=plan.follow_up_question,
        question_type=parent.question_type,
        ideal_answer=plan.reference,
        key_points=plan.key_points,
        misconceptions=list(parent.misconceptions or []) if plan.follow_up_kind == "clarify" else [],
        category="follow_up",
        selection_reason=f"Follow-up: {plan.rationale}",
        focus_skills=list(parent.focus_skills or []),
        parent_question_id=parent.id,
        follow_up_kind=plan.follow_up_kind,
    )
    db.add(follow_up)
    db.flush()
    return follow_up


def _adjust_next_question(db: Session, session: InterviewSession, current: InterviewQuestion) -> InterviewQuestion | None:
    """Swap the next unanswered core question for a harder/easier one when the evidence is clear."""
    adjustments = sum(1 for q in session.questions if (q.selection_reason or "").startswith(adaptive.ADJUSTED_PREFIX))
    if adjustments >= adaptive.MAX_ADJUSTMENTS:
        return None
    scores = [q.answer.evaluation.score for q in session.questions
              if q.category != "follow_up" and q.answer is not None and q.answer.evaluation is not None]
    target = adaptive.target_difficulty(scores, session.difficulty)
    if target is None:
        return None
    upcoming = sorted((q for q in session.questions if q.position > current.position and q.answer is None
                       and q.category in ("core", "behavioral") and q.bank_question_id is not None),
                      key=lambda q: q.position)
    if not upcoming:
        return None
    nxt = upcoming[0]
    bank_item = db.get(QuestionBankItem, nxt.bank_question_id)
    if bank_item is None or bank_item.difficulty == target:
        return None
    used = {q.text.lower() for q in session.questions}
    roles = match_roles(session.target_role)
    options = [b for b in db.scalars(select(QuestionBankItem).where(QuestionBankItem.is_active.is_(True)))
               if b.kind.value == "generic" and b.question_type is nxt.question_type and b.difficulty == target
               and _role_ok(b, roles) and b.ideal_answer and b.text.lower() not in used]
    if not options:
        return None
    wanted = {t.lower() for t in (bank_item.skill_tags or [])}
    options.sort(key=lambda b: (-len(wanted & {t.lower() for t in (b.skill_tags or [])}), b.text))
    choice = options[0]
    direction = "harder" if adaptive._ORDER.index(target) > adaptive._ORDER.index(session.difficulty) else "easier"
    nxt.text = choice.text
    nxt.ideal_answer = choice.ideal_answer
    nxt.key_points = list(choice.key_points or [])
    nxt.misconceptions = list(choice.misconceptions or [])
    nxt.bank_question_id = choice.id
    nxt.focus_skills = list(choice.skill_tags or [])[:3]
    nxt.selection_reason = (f"{adaptive.ADJUSTED_PREFIX} your answers so far averaged "
                            f"{round(sum(scores) / len(scores))}/100, so this question is {direction} ({target.value}).")
    db.flush()
    return nxt


def get_evaluation(db: Session, user: User, interview_id: uuid.UUID, question_id: uuid.UUID) -> Evaluation:
    session = get_owned_interview(db, user, interview_id)
    question = get_question(session, question_id)
    if question.answer is None or question.answer.evaluation is None:
        raise _err("EVALUATION_NOT_FOUND", "This answer has not been evaluated yet.", 404)
    return question.answer.evaluation


# --- complete / abandon ----------------------------------------------------------------------------


def _mean(values: list[int]) -> int:
    return round_half_up(sum(values) / len(values)) if values else 0


def compute_breakdown(evaluations: list[Evaluation]) -> dict[str, int]:
    def mean_of(attr: str) -> int:
        return _mean([getattr(e, attr) for e in evaluations if getattr(e, attr) is not None])

    breakdown = {
        "structure": mean_of("structure_score"),
        "relevance": mean_of("relevance_score"),
        "clarity": mean_of("clarity_score"),
        "technical_depth": mean_of("technical_depth_score"),
    }
    breakdown["communication"] = round_half_up((breakdown["clarity"] + breakdown["structure"]) / 2)
    return breakdown


def complete(db: Session, user: User, interview_id: uuid.UUID) -> InterviewSession:
    session = get_owned_interview(db, user, interview_id)
    if session.status is SessionStatus.COMPLETED:
        return session  # idempotent: the stored results are returned unchanged
    if session.status is SessionStatus.ABANDONED:
        raise _not_active()
    missing = [q.position for q in session.questions if q.answer is None or q.answer.evaluation is None]
    if missing:
        raise _err("INTERVIEW_INCOMPLETE", "Every question must be answered and evaluated before finishing.", 409,
                   details=[{"field": "questions", "issue": "unevaluated_positions", "positions": missing}])

    evaluations = [q.answer.evaluation for q in session.questions]
    breakdown = compute_breakdown(evaluations)
    strength, improvement, recommendations = templates.interview_texts(breakdown)
    session.overall_score = _mean([e.score for e in evaluations])
    session.breakdown = breakdown
    session.additional_strength = strength
    session.additional_improvement = improvement
    session.recommendations = recommendations
    session.generated_by = "rules"
    session.status = SessionStatus.COMPLETED
    session.completed_at = _now()
    db.commit()
    completed = get_owned_interview(db, user, interview_id)
    try:
        from app.services import improvement_service

        improvement_service.generate_for_session(db, user, completed)
    except Exception:  # the plan can be generated later on request; never block completion
        logger.exception("Improvement plan generation failed for interview %s", interview_id)
        db.rollback()
    return completed


def abandon(db: Session, user: User, interview_id: uuid.UUID) -> InterviewSession:
    session = get_owned_interview(db, user, interview_id)
    if session.status is SessionStatus.COMPLETED:
        raise _not_active()
    if session.status is SessionStatus.IN_PROGRESS:
        session.status = SessionStatus.ABANDONED
        db.commit()
    return session


# --- history and performance --------------------------------------------------------------------


def _completed_query(user: User):
    return select(InterviewSession).where(
        InterviewSession.user_id == user.id, InterviewSession.status == SessionStatus.COMPLETED
    )


def history(db: Session, user: User, *, interview_type: InterviewType | None, limit: int, offset: int):
    query = _completed_query(user)
    if interview_type is not None:
        query = query.where(InterviewSession.interview_type == interview_type)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = list(db.scalars(query.order_by(InterviewSession.completed_at.desc()).limit(limit).offset(offset)))
    return items, total


def skill_scores(db: Session, user: User) -> tuple[list[dict], int]:
    sessions = list(db.scalars(_completed_query(user)))
    breakdowns = [s.breakdown for s in sessions if s.breakdown]
    if not breakdowns:
        return [], 0
    skills = [
        {"key": key, "label": templates.SKILL_LABELS[key], "score": _mean([b[key] for b in breakdowns if key in b])}
        for key in templates.SKILL_ORDER
    ]
    skills.sort(key=lambda s: (-s["score"], templates.SKILL_ORDER.index(s["key"])))
    return skills, len(breakdowns)


def summary(db: Session, user: User, trend_limit: int) -> dict:
    sessions = list(db.scalars(_completed_query(user).order_by(InterviewSession.completed_at.desc())))
    skills, _ = skill_scores(db, user)
    scores = [s.overall_score for s in sessions if s.overall_score is not None]
    trend = [
        {"interview_id": s.id, "completed_at": s.completed_at, "overall_score": s.overall_score}
        for s in reversed(sessions[:trend_limit])
    ]
    return {
        "interviews_completed": len(sessions),
        "average_score": _mean(scores) if scores else None,
        "strongest_skill": skills[0] if skills else None,
        "weakest_skill": skills[-1] if skills else None,
        "trend": trend,
    }


def reset_user_data(db: Session, user: User) -> tuple[int, int, list[str]]:
    """Delete the user's CVs and interviews (keeps the account). Returns storage keys to delete."""
    from app.models import CandidateProfile

    cvs = list(db.scalars(select(CV).where(CV.user_id == user.id)))
    sessions = list(db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)))
    keys = [cv.storage_path for cv in cvs]
    # The profile is derived from the CVs, so it is personal data that goes too.
    # Improvement plans are removed with their interviews (ON DELETE CASCADE).
    for profile in db.scalars(select(CandidateProfile).where(CandidateProfile.user_id == user.id)):
        db.delete(profile)
    for session in sessions:
        db.delete(session)
    for cv in cvs:
        db.delete(cv)
    db.commit()
    return len(cvs), len(sessions), keys

