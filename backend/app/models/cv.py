import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CVFileType, CVStatus, string_enum

if TYPE_CHECKING:
    from app.models.interview import InterviewSession
    from app.models.user import User

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")
MAX_CV_BYTES = 5 * 1024 * 1024


class CV(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An uploaded CV: metadata, private storage key, extracted text and the
    rule-based extraction results (skills and best-effort profile lines).

    The file itself is NOT stored in the database. `storage_path` is a random
    file name relative to CV_STORAGE_DIR; it is never returned by the API.
    The extracted lists are 1:1 with the CV, so they are columns here instead of
    the spec's separate cv_profiles / cv_skills tables.
    """

    __tablename__ = "cvs"
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        CheckConstraint(f"file_size_bytes <= {MAX_CV_BYTES}", name="file_size_max"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500), unique=True)
    file_type: Mapped[CVFileType] = mapped_column(string_enum(CVFileType, "file_type"))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[CVStatus] = mapped_column(
        string_enum(CVStatus, "status"), default=CVStatus.UPLOADED
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    experience: Mapped[list[str]] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    education: Mapped[list[str]] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    projects: Mapped[list[str]] = mapped_column(JSONType, default=list, server_default=text("'[]'"))
    extractor_version: Mapped[str | None] = mapped_column(String(30))

    user: Mapped["User"] = relationship(back_populates="cvs")
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="cv", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<CV id={self.id} status={self.status}>"
