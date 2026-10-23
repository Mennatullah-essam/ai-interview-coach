from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.auth import RefreshToken
    from app.models.cv import CV
    from app.models.interview import InterviewSession


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered candidate.

    The API calls `full_name` "name". Emails are stored lower-cased (enforced by
    a CHECK constraint) so the unique constraint is effectively case-insensitive.
    `password_hash` is nullable only for rows created before authentication
    existed; such accounts cannot log in until a password is set.
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    cvs: Mapped[list["CV"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id}>"
