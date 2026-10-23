from sqlalchemy import Boolean, String, Text, true
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.cv import JSONType
from app.models.enums import Difficulty, QuestionKind, QuestionType, string_enum


class QuestionBankItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Curated, reusable interview question with a reference answer (spec D4).

    Shared by all users (reference data, not user data). Seeded from
    app/data/question_bank.json by scripts/seed_question_bank.py.

    role_tags: preset role names, or "general" for role-agnostic questions.
    skill_tags: skills the question is about; ranked against the CV's skills.
    ideal_answer: the curated reference answer used for scoring; only shown to
    the user after their answer has been evaluated.
    key_points: 3-6 short phrases a good answer should cover.
    """

    __tablename__ = "question_bank"

    kind: Mapped[QuestionKind] = mapped_column(
        string_enum(QuestionKind, "kind"),
        default=QuestionKind.GENERIC,
        server_default=QuestionKind.GENERIC.value,
    )
    text: Mapped[str] = mapped_column(String(1000), unique=True)
    question_type: Mapped[QuestionType] = mapped_column(
        string_enum(QuestionType, "question_type")
    )
    difficulty: Mapped[Difficulty | None] = mapped_column(
        string_enum(Difficulty, "difficulty")
    )
    role_tags: Mapped[list[str]] = mapped_column(
        JSONType, default=lambda: ["general"], server_default=sql_text("'[\"general\"]'")
    )
    skill_tags: Mapped[list[str]] = mapped_column(JSONType, default=list, server_default=sql_text("'[]'"))
    ideal_answer: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list[str]] = mapped_column(JSONType, default=list, server_default=sql_text("'[]'"))
    # Known wrong statements for this question: [{"pattern": regex, "explanation": str}].
    # Used by the technical-accuracy dimension of the evaluation.
    misconceptions: Mapped[list[dict]] = mapped_column(JSONType, default=list, server_default=sql_text("'[]'"))
    source_note: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<QuestionBankItem id={self.id} type={self.question_type}>"
