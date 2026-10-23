"""Milestone 4/5 tables: the reviewed candidate profile, improvement plans and agent decisions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.cv import JSONType
from app.models.enums import ProfileStatus, string_enum

if TYPE_CHECKING:
    from app.models.user import User


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One structured profile per user (schema: app/schemas/profile.py ProfileData).

    Built from the newest CV as a *draft*; it influences interview selection only
    after the candidate reviews and confirms it.
    """

    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    cv_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cvs.id", ondelete="SET NULL"), index=True)
    status: Mapped[ProfileStatus] = mapped_column(
        string_enum(ProfileStatus, "status"), default=ProfileStatus.DRAFT
    )
    data: Mapped[dict] = mapped_column(JSONType)
    extractor_version: Mapped[str | None] = mapped_column(String(30))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()


class ImprovementPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Personalised practice plan generated when an interview is completed."""

    __tablename__ = "improvement_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), unique=True
    )
    target_role: Mapped[str] = mapped_column(String(100))
    plan_version: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict] = mapped_column(JSONType)


class AgentDecisionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit trail of the adaptive interview agent (Milestone 5).

    One row per decision about an evaluated question: kind "follow_up" (continue /
    clarify / request_example / probe_concept / deepen) or "difficulty" (a later
    question was adjusted). Stores who proposed it (rules or llm), the policy
    result and the evidence, never the prompt or the raw model output.
    """

    __tablename__ = "agent_decisions"
    __table_args__ = (UniqueConstraint("question_id", "kind", name="uq_agent_decisions_question_kind"),)

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12), default="follow_up")
    action: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(8), default="rules")
    policy: Mapped[str] = mapped_column(String(40), default="accepted")
    llm_status: Mapped[str | None] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    target_concept: Mapped[str | None] = mapped_column(String(200))
    result_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="SET NULL"), index=True
    )
