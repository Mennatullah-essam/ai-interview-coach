"""Allowed values for status/category columns.

Values come from the frontend's options (src/data/constants.js). They are
stored as short lowercase strings with a CHECK constraint (not PostgreSQL
native ENUM types), which keeps later migrations simple.
"""

import enum

from sqlalchemy import Enum


class CVFileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"


class CVStatus(str, enum.Enum):
    UPLOADED = "uploaded"  # file saved, text not extracted yet
    PARSED = "parsed"  # text extracted successfully
    FAILED = "failed"  # extraction failed


class QuestionType(str, enum.Enum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"


class InterviewType(str, enum.Enum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    MIXED = "mixed"


class Difficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"  # user chose "Exit"; excluded from history and stats


class QuestionKind(str, enum.Enum):
    GENERIC = "generic"  # a fixed question
    SKILL_TEMPLATE = "skill_template"  # contains {skill}, filled from the CV
    PROJECT_TEMPLATE = "project_template"  # contains {project}, filled from the reviewed profile


class ProfileStatus(str, enum.Enum):
    DRAFT = "draft"  # extracted from a CV, not yet reviewed by the candidate
    CONFIRMED = "confirmed"  # reviewed; used to personalise interviews


def string_enum(enum_class: type[enum.Enum], name: str) -> Enum:
    """VARCHAR column + CHECK constraint storing the enum's *values*."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
