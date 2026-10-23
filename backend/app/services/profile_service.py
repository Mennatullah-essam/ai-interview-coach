"""Create, refresh, review and read the candidate profile (Milestone 4, feature 1).

Rules
* A new CV produces a *draft* profile. Items the candidate added or changed
  earlier (source "user") are kept; CV-derived items are refreshed.
* Saving from the review screen recomputes provenance on the server: unchanged
  items keep their source and evidence, new or edited items become "user".
* Only a *confirmed* profile personalises interviews.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.intelligence.knowledge import skill_catalog
from app.intelligence.profile_extraction import EXTRACTOR_VERSION, build_profile
from app.models import CV, CandidateProfile, User
from app.models.enums import ProfileStatus
from app.schemas.profile import ProfileData


def get_profile(db: Session, user: User) -> CandidateProfile | None:
    return db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))


def _key(item) -> str:
    for attr in ("name", "text", "title"):
        value = getattr(item, attr, None)
        if value:
            return value.strip().lower()
    return ""


def _keep_user_items(new_list: list, old_list: list) -> list:
    """Add the candidate's own items from the old profile to a freshly extracted list."""
    keys = {_key(item) for item in new_list}
    return new_list + [item for item in old_list if item.source == "user" and _key(item) not in keys]


def merge_user_edits(fresh: ProfileData, previous: ProfileData) -> ProfileData:
    for field in ("technical_skills", "soft_skills", "expertise_areas", "experience", "education",
                  "projects", "achievements", "career_interests"):
        setattr(fresh, field, _keep_user_items(getattr(fresh, field), getattr(previous, field)))
    for field in ("target_role", "experience_level", "years_experience"):
        if getattr(previous, field).source == "user":
            setattr(fresh, field, getattr(previous, field))
    return fresh


def refresh_from_cv(db: Session, user: User, cv: CV) -> CandidateProfile:
    """Rebuild the draft profile from a CV, keeping the candidate's own edits."""
    profile = get_profile(db, user)
    previous = ProfileData.model_validate(profile.data) if profile else None
    explicit_role = previous.target_role.value if previous and previous.target_role.source == "user" else None
    fresh = build_profile(cv.extracted_text, explicit_target_role=explicit_role)
    if previous is not None:
        fresh = merge_user_edits(fresh, previous)
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    profile.cv_id = cv.id
    profile.data = fresh.model_dump(mode="json")
    profile.status = ProfileStatus.DRAFT
    profile.extractor_version = EXTRACTOR_VERSION
    profile.confirmed_at = None
    db.commit()
    db.refresh(profile)
    return profile


def _with_provenance(submitted: list, previous: list) -> list:
    old = {_key(item): item for item in previous}
    result = []
    for item in submitted:
        before = old.get(_key(item))
        if before is not None and before.model_dump(exclude={"source", "evidence"}) == item.model_dump(exclude={"source", "evidence"}):
            result.append(before)  # unchanged: keep original source and evidence
        else:
            changes = {"source": "user"}
            if "evidence" in type(item).model_fields:
                changes["evidence"] = "Added or edited by you."
            result.append(item.model_copy(update=changes))
    return result


def _normalise_skills(items: list) -> list:
    catalog = skill_catalog()
    seen, result = set(), []
    for item in items:
        canonical = catalog.normalize(item.name) or item.name
        if canonical.lower() in seen:
            continue
        seen.add(canonical.lower())
        result.append(item.model_copy(update={"name": canonical, "category": catalog.category_of.get(canonical, item.category)}))
    return result


def update_profile(db: Session, user: User, submitted: ProfileData, *, confirm: bool) -> CandidateProfile:
    profile = get_profile(db, user)
    if profile is None:
        profile = CandidateProfile(user_id=user.id, data=ProfileData().model_dump(mode="json"))
        db.add(profile)
    previous = ProfileData.model_validate(profile.data)
    updated = submitted.model_copy(deep=True)
    for field in ("technical_skills", "soft_skills", "expertise_areas", "experience", "education",
                  "projects", "achievements", "career_interests"):
        setattr(updated, field, _with_provenance(getattr(updated, field), getattr(previous, field)))
    updated.technical_skills = _normalise_skills(updated.technical_skills)
    updated.soft_skills = _normalise_skills(updated.soft_skills)
    for field in ("target_role", "experience_level", "years_experience"):
        new_value, old_value = getattr(updated, field), getattr(previous, field)
        if new_value.value == old_value.value:
            setattr(updated, field, old_value)
        elif new_value.value is not None:
            setattr(updated, field, new_value.model_copy(update={"source": "user", "evidence": "Set by you."}))
        else:
            setattr(updated, field, type(new_value)())
    updated.warnings = [] if confirm else previous.warnings
    profile.data = updated.model_dump(mode="json")
    if confirm:
        profile.status = ProfileStatus.CONFIRMED
        profile.confirmed_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    return profile


def confirmed_profile(db: Session, user: User) -> ProfileData | None:
    """The profile used for personalisation, or None if not reviewed yet."""
    profile = get_profile(db, user)
    if profile is None or profile.status is not ProfileStatus.CONFIRMED:
        return None
    return ProfileData.model_validate(profile.data)


def require_profile(db: Session, user: User) -> CandidateProfile:
    profile = get_profile(db, user)
    if profile is None:
        raise AppError("PROFILE_NOT_FOUND", "Upload a CV first to create your profile.", 404)
    return profile
