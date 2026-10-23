"""Structured candidate profile (Milestone 4, feature 1).

Every piece of information carries its provenance:
  extracted  found in the CV text (with the line it came from as evidence)
  inferred   derived by a documented rule (with the reasoning as evidence)
  user       added or changed by the candidate during review
The same models validate what is stored and what the API returns/accepts.
"""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Timestamp

Source = Literal["extracted", "inferred", "user"]
ExperienceLevel = Literal["student", "entry", "junior", "mid", "senior"]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Medium = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)]
Evidence = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillItem(_Base):
    name: Short
    category: str | None = None
    source: Source = "user"
    evidence: Evidence | None = None


class TextItem(_Base):
    text: Medium
    source: Source = "user"
    evidence: Evidence | None = None


class ExperienceEntry(_Base):
    title: Medium
    organization: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    period: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    responsibilities: list[Medium] = Field(default_factory=list, max_length=8)
    source: Source = "user"


class ProjectEntry(_Base):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    description: Long | None = None
    technologies: list[Short] = Field(default_factory=list, max_length=20)
    source: Source = "user"


class InferredValue(_Base):
    value: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    source: Source | None = None
    evidence: Evidence | None = None


class LevelValue(_Base):
    value: ExperienceLevel | None = None
    source: Source | None = None
    evidence: Evidence | None = None


class YearsValue(_Base):
    value: float | None = Field(default=None, ge=0, le=60)
    source: Source | None = None
    evidence: Evidence | None = None


class ProfileData(_Base):
    target_role: InferredValue = Field(default_factory=InferredValue)
    experience_level: LevelValue = Field(default_factory=LevelValue)
    years_experience: YearsValue = Field(default_factory=YearsValue)
    technical_skills: list[SkillItem] = Field(default_factory=list, max_length=80)
    soft_skills: list[SkillItem] = Field(default_factory=list, max_length=30)
    expertise_areas: list[SkillItem] = Field(default_factory=list, max_length=15)
    experience: list[ExperienceEntry] = Field(default_factory=list, max_length=15)
    education: list[TextItem] = Field(default_factory=list, max_length=10)
    projects: list[ProjectEntry] = Field(default_factory=list, max_length=15)
    achievements: list[TextItem] = Field(default_factory=list, max_length=15)
    career_interests: list[TextItem] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class ProfileUpdateIn(_Base):
    """What the review screen sends. Provenance is recomputed on the server."""

    profile: ProfileData
    confirm: bool = True


class ProfileOut(BaseModel):
    id: uuid.UUID
    status: Literal["draft", "confirmed"]
    cv_id: uuid.UUID | None
    profile: ProfileData
    extractor_version: str | None
    confirmed_at: Timestamp | None
    updated_at: Timestamp
