"""Interview session -> questions -> answer -> evaluation.

Results and history are not separate tables: a completed session stores its
result summary (overall score, breakdown, highlight strings, recommendations)
in its own columns, written once when it is completed, and a user's history
is their completed sessions ordered by date. Skill scores are computed from
the stored breakdowns with a query, not stored a second time.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    Difficulty,
    InterviewType,
    QuestionType,
    SessionStatus,
    string_enum,
)

if TYPE_CHECKING:
    from app.models.cv import CV
    from app.models.question_bank import QuestionBankItem
    from app.models.user import User

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite in tests).
JSONList = JSON().with_variant(JSONB(), "postgresql")
EMPTY_LIST = text("'[]'")


def _score_check(column: str) -> CheckConstraint:
    return CheckConstraint(f"{column} BETWEEN 0 AND 100", name=f"{column}_range")


class InterviewSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One practice interview and its setup (role, type, difficulty, count).

    The result columns (overall_score, breakdown, additional_*, recommendations,
    generated_by) are written once, in the same transaction that marks the
    session completed, so history and results never need re-computing.
    """

    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint("question_count > 0", name="question_count_positive"),
        _score_check("overall_score"),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="completed_at_matches_status",
        ),
        # History: "this user's sessions, newest first".
        Index("ix_interview_sessions_user_id_created_at", "user_id", "created_at"),
        # Completed-history and stats queries.
        Index("ix_interview_sessions_user_id_status_completed_at", "user_id", "status", "completed_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Keep the interview if the CV is deleted later.
    cv_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cvs.id", ondelete="SET NULL"), index=True
    )
    target_role: Mapped[str] = mapped_column(String(100))
    interview_type: Mapped[InterviewType] = mapped_column(
        string_enum(InterviewType, "interview_type")
    )
    difficulty: Mapped[Difficulty] = mapped_column(string_enum(Difficulty, "difficulty"))
    question_count: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[SessionStatus] = mapped_column(
        string_enum(SessionStatus, "status"), default=SessionStatus.IN_PROGRESS
    )
    overall_score: Mapped[int | None] = mapped_column(SmallInteger)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {"structure": int, "relevance": int, "clarity": int, "technical_depth": int, "communication": int}
    breakdown: Mapped[dict | None] = mapped_column(JSONList)
    additional_strength: Mapped[str | None] = mapped_column(Text)
    additional_improvement: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[list[str] | None] = mapped_column(JSONList)
    generated_by: Mapped[str | None] = mapped_column(String(8))  # "rules" in the MVP
    # Milestone 4: personalisation and adaptivity settings.
    adaptive: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    max_follow_ups: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    personalized: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    job_description: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="interview_sessions")
    cv: Mapped["CV | None"] = relationship(back_populates="interview_sessions")
    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InterviewQuestion.position",
    )

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} status={self.status}>"


class InterviewQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A question asked in a session. `id` is the stable identifier;
    `position` is only the display order (1, 2, 3, ...)."""

    __tablename__ = "interview_questions"
    __table_args__ = (
        UniqueConstraint("session_id", "position"),
        CheckConstraint("position >= 1", name="position_positive"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE")
    )
    # NULL when the question was generated by AI instead of taken from the bank.
    bank_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_bank.id", ondelete="SET NULL"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column(
        string_enum(QuestionType, "question_type")
    )
    # Snapshot of the bank's reference answer and key points at creation time.
    # Secret until the question is evaluated; never returned before that.
    ideal_answer: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list[str]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    misconceptions: Mapped[list[dict]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    # Milestone 4: why this question was chosen and what it assesses.
    # category: core | cv_skill | project | skill_gap | behavioral | follow_up
    category: Mapped[str | None] = mapped_column(String(20))
    selection_reason: Mapped[str | None] = mapped_column(Text)
    focus_skills: Mapped[list[str]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    # Follow-ups point at the question they follow up on.
    parent_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="CASCADE"), index=True
    )
    follow_up_kind: Mapped[str | None] = mapped_column(String(12))  # clarify | example | deeper

    session: Mapped["InterviewSession"] = relationship(back_populates="questions")
    bank_question: Mapped["QuestionBankItem | None"] = relationship()
    answer: Mapped["Answer | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<InterviewQuestion id={self.id} position={self.position}>"


class Answer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The candidate's answer to one question (at most one per question;
    re-submitting updates the row)."""

    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint("length(answer_text) > 0", name="answer_text_not_empty"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="CASCADE"), unique=True
    )
    answer_text: Mapped[str] = mapped_column(Text)

    question: Mapped["InterviewQuestion"] = relationship(back_populates="answer")
    evaluation: Mapped["Evaluation | None"] = relationship(
        back_populates="answer", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Answer id={self.id}>"


class Evaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Automated feedback for one answer: overall score, four category scores,
    strengths, weaknesses, tip and the revealed ideal answer.

    "structure" replaced the former "confidence" category (API spec D5: the app
    must not claim to measure psychological confidence from text).
    feedback_source / scoring_version / model_info record exactly how the
    evaluation was produced, e.g. the "lexical" fallback versus the "sbert" model.
    """

    __tablename__ = "evaluations"
    __table_args__ = (
        _score_check("score"),
        _score_check("relevance_score"),
        _score_check("clarity_score"),
        _score_check("technical_depth_score"),
        _score_check("structure_score"),
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), unique=True
    )
    score: Mapped[int] = mapped_column(SmallInteger)
    relevance_score: Mapped[int | None] = mapped_column(SmallInteger)
    clarity_score: Mapped[int | None] = mapped_column(SmallInteger)
    technical_depth_score: Mapped[int | None] = mapped_column(SmallInteger)
    structure_score: Mapped[int | None] = mapped_column(SmallInteger)
    strengths: Mapped[list[str]] = mapped_column(JSONList, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSONList, default=list)
    improvement_tip: Mapped[str | None] = mapped_column(Text)
    ideal_answer: Mapped[str | None] = mapped_column(Text)
    feedback_source: Mapped[str] = mapped_column(String(8), default="rules", server_default="rules")
    scoring_version: Mapped[str] = mapped_column(String(30), default="legacy", server_default="legacy")
    model_info: Mapped[dict] = mapped_column(JSONList, default=dict, server_default=text("'{}'"))
    semantic_similarity: Mapped[float | None] = mapped_column(Numeric(5, 4))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    # Milestone 4: six separate dimensions [{key, label, score|null, weight, explanation}],
    # concepts the answer did not cover, concrete suggestions and how the score was reached.
    dimensions: Mapped[list[dict] | None] = mapped_column(JSONList)
    missing_concepts: Mapped[list[str]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    suggestions: Mapped[list[str]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    explanation: Mapped[str | None] = mapped_column(Text)
    # Milestone 5: evidence behind the scores. concept_evidence = [{concept, status, evidence}],
    # status demonstrated | partial | mentioned | missing; claims are quotes from the answer.
    concept_evidence: Mapped[list[dict]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    unsupported_claims: Mapped[list[str]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    incorrect_claims: Mapped[list[dict]] = mapped_column(JSONList, default=list, server_default=EMPTY_LIST)
    evidence_level: Mapped[str | None] = mapped_column(String(12))

    answer: Mapped["Answer"] = relationship(back_populates="evaluation")

    def __repr__(self) -> str:
        return f"<Evaluation id={self.id} score={self.score}>"
