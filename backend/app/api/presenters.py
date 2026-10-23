"""Turn ORM objects into the response shapes of the API specification (section 17).

Hidden data never leaves through here: storage paths, extracted CV text,
reference answers before evaluation, key points and scoring diagnostics.
"""

from app.models import CV, Answer, Evaluation, InterviewQuestion, InterviewSession, User
from app.models.enums import CVStatus
from app.schemas.auth import UserOut
from app.schemas.intelligence import ImprovementPlanOut
from app.schemas.interviews import (
    AnswerOut,
    Breakdown,
    CategoryScores,
    CVDetailOut,
    CVExtracted,
    CVOut,
    EvaluationOut,
    InterviewConfigOut,
    InterviewCreatedOut,
    InterviewStateOut,
    InterviewSummary,
    Progress,
    QuestionOut,
    ResultItem,
    ResultItemQuestion,
    ResultsOut,
)
from app.schemas.profile import ProfileData, ProfileOut


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.full_name, email=user.email, created_at=user.created_at)


def cv_out(cv: CV) -> CVOut:
    status = cv.status.value if isinstance(cv.status, CVStatus) else str(cv.status)
    return CVOut(
        id=cv.id,
        original_filename=cv.original_filename,
        extension=cv.file_type.value,
        size_bytes=cv.file_size_bytes,
        parse_status=status,
        created_at=cv.created_at,
    )


def cv_detail_out(cv: CV) -> CVDetailOut:
    return CVDetailOut(
        cv=cv_out(cv),
        extracted=CVExtracted(
            skills=list(cv.skills or []),
            experience=list(cv.experience or []),
            education=list(cv.education or []),
            projects=list(cv.projects or []),
        ),
    )


def _question_state(question: InterviewQuestion) -> str:
    if question.answer is None:
        return "pending"
    return "evaluated" if question.answer.evaluation is not None else "answered"


def question_out(question: InterviewQuestion, with_state: bool = False) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        position=question.position,
        text=question.text,
        type=question.question_type,
        state=_question_state(question) if with_state else None,
        category=question.category,
        reason=question.selection_reason,
        focus_skills=list(question.focus_skills or []),
        parent_question_id=question.parent_question_id,
        follow_up_kind=question.follow_up_kind,
    )


def _config(session: InterviewSession) -> InterviewConfigOut:
    return InterviewConfigOut(
        cv_id=session.cv_id,
        target_role=session.target_role,
        interview_type=session.interview_type,
        difficulty=session.difficulty,
        question_count=session.question_count,
        adaptive=bool(session.adaptive),
        max_follow_ups=session.max_follow_ups or 0,
        personalized=bool(session.personalized),
        has_job_description=bool(session.job_description),
    )


def interview_created_out(session: InterviewSession) -> InterviewCreatedOut:
    return InterviewCreatedOut(
        id=session.id,
        status=session.status.value,
        config=_config(session),
        questions=[question_out(q) for q in session.questions],
        created_at=session.created_at,
    )


def interview_state_out(session: InterviewSession) -> InterviewStateOut:
    states = [_question_state(q) for q in session.questions]
    current = next((q.position for q, s in zip(session.questions, states) if s != "evaluated"), None)
    return InterviewStateOut(
        id=session.id,
        status=session.status.value,
        config=_config(session),
        questions=[question_out(q, with_state=True) for q in session.questions],
        created_at=session.created_at,
        completed_at=session.completed_at,
        progress=Progress(
            answered=sum(s != "pending" for s in states),
            evaluated=sum(s == "evaluated" for s in states),
            total=len(states),
        ),
        current_position=current,
    )


def answer_out(session: InterviewSession, answer: Answer) -> AnswerOut:
    return AnswerOut(
        id=answer.id,
        interview_id=session.id,
        question_id=answer.question_id,
        answer_text=answer.answer_text,
        char_count=len(answer.answer_text),
        submitted_at=answer.created_at,
        updated_at=answer.updated_at,
    )


def _dimensions(evaluation: Evaluation) -> list[dict]:
    if evaluation.dimensions:
        return evaluation.dimensions
    # Evaluations stored before Milestone 4 only have the four original categories.
    legacy = [("relevance", "Relevance", evaluation.relevance_score),
              ("structure", "Structure", evaluation.structure_score),
              ("communication", "Communication", evaluation.clarity_score)]
    return [{"key": k, "label": label, "score": v, "weight": 0.0,
             "explanation": "Scored with an earlier version of the evaluator."} for k, label, v in legacy if v is not None]


def evaluation_out(evaluation: Evaluation, question_id, question: InterviewQuestion | None = None,
                   adaptation: dict | None = None) -> EvaluationOut:
    adaptation = adaptation or {}
    follow_up = adaptation.get("follow_up")
    replaced = adaptation.get("replaced")
    decision = adaptation.get("decision")
    return EvaluationOut(
        id=evaluation.id,
        question_id=question_id,
        overall_score=evaluation.score,
        category_scores=CategoryScores(
            relevance=evaluation.relevance_score or 0,
            clarity=evaluation.clarity_score or 0,
            technical_depth=evaluation.technical_depth_score or 0,
            structure=evaluation.structure_score or 0,
        ),
        strengths=list(evaluation.strengths or []),
        weaknesses=list(evaluation.weaknesses or []),
        improvement_tip=evaluation.improvement_tip or "",
        ideal_answer=evaluation.ideal_answer or "",
        feedback_source=evaluation.feedback_source,
        scoring_version=evaluation.scoring_version,
        created_at=evaluation.created_at,
        dimensions=_dimensions(evaluation),
        missing_concepts=list(evaluation.missing_concepts or []),
        suggestions=list(evaluation.suggestions or []),
        explanation=evaluation.explanation,
        ideal_outline=list(question.key_points or []) if question is not None else [],
        follow_up=question_out(follow_up) if follow_up is not None else None,
        replaced_question=question_out(replaced) if replaced is not None else None,
        concept_evidence=list(evaluation.concept_evidence or []),
        demonstrated_concepts=[c["concept"] for c in (evaluation.concept_evidence or [])
                               if c.get("status") in ("demonstrated", "partial")],
        unsupported_claims=list(evaluation.unsupported_claims or []),
        incorrect_claims=[{"explanation": c.get("explanation", ""), "evidence": c.get("evidence")}
                          for c in (evaluation.incorrect_claims or [])],
        evidence_level=evaluation.evidence_level,
        agent_decision=None if decision is None else {
            "action": decision.action, "rationale": decision.rationale, "evidence": list(decision.evidence or []),
            "source": decision.source, "target_concept": decision.target_concept, "policy": decision.policy},
    )


def summary_out(session: InterviewSession) -> InterviewSummary:
    return InterviewSummary(
        id=session.id,
        completed_at=session.completed_at,
        target_role=session.target_role,
        interview_type=session.interview_type,
        difficulty=session.difficulty,
        question_count=session.question_count,
        overall_score=session.overall_score,
        status=session.status.value,
    )


def results_out(session: InterviewSession, decisions: dict | None = None) -> ResultsOut:
    items = []
    for q in session.questions:
        if q.answer is None or q.answer.evaluation is None:
            continue
        items.append(
            ResultItem(
                position=q.position,
                question=ResultItemQuestion(id=q.id, text=q.text, type=q.question_type, category=q.category,
                                            reason=q.selection_reason, parent_question_id=q.parent_question_id),
                answer_text=q.answer.answer_text,
                evaluation=evaluation_out(q.answer.evaluation, q.id, q, {"decision": (decisions or {}).get(q.id)}),
            )
        )
    return ResultsOut(
        interview=summary_out(session),
        breakdown=Breakdown(**session.breakdown),
        additional_strength=session.additional_strength or "",
        additional_improvement=session.additional_improvement or "",
        recommendations=list(session.recommendations or []),
        generated_by=session.generated_by or "rules",
        items=items,
    )


def plan_out(plan) -> ImprovementPlanOut:
    return ImprovementPlanOut(id=plan.id, interview_id=plan.interview_id, target_role=plan.target_role,
                              plan_version=plan.plan_version, created_at=plan.created_at,
                              updated_at=plan.updated_at, plan=plan.data)


def profile_out(profile) -> ProfileOut:
    return ProfileOut(id=profile.id, status=profile.status.value, cv_id=profile.cv_id,
                      profile=ProfileData.model_validate(profile.data), extractor_version=profile.extractor_version,
                      confirmed_at=profile.confirmed_at, updated_at=profile.updated_at)
