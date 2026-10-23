"""Candidate profile: read, review/correct and confirm (Milestone 4, feature 1).

Only the signed-in user's own profile is ever reachable: there is no profile id
in any path, the profile is looked up from the authenticated user.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.presenters import plan_out, profile_out
from app.core.errors import AppError
from app.db.session import get_db
from app.models import CV, User
from app.schemas.intelligence import ImprovementPlanOut
from app.schemas.profile import ProfileOut, ProfileUpdateIn
from app.services import improvement_service, profile_service

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The structured profile built from your newest CV (status draft until you confirm it)."""
    profile = profile_service.get_profile(db, user)
    if profile is None:
        latest = db.scalar(select(CV).where(CV.user_id == user.id).order_by(CV.created_at.desc()))
        if latest is None:
            raise AppError("PROFILE_NOT_FOUND", "Upload a CV first to create your profile.", 404)
        profile = profile_service.refresh_from_cv(db, user, latest)  # e.g. CVs uploaded before Milestone 4
    return profile_out(profile)


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save your corrections. With confirm=true the profile starts personalising interviews."""
    return profile_out(profile_service.update_profile(db, user, body.profile, confirm=body.confirm))


@router.post("/profile/rebuild", response_model=ProfileOut)
def rebuild_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-extract from your newest CV, keeping items you added yourself (back to draft)."""
    latest = db.scalar(select(CV).where(CV.user_id == user.id).order_by(CV.created_at.desc()))
    if latest is None:
        raise AppError("CV_NOT_FOUND", "Upload a CV first.", 404)
    return profile_out(profile_service.refresh_from_cv(db, user, latest))


@router.get("/improvement-plans/latest", response_model=ImprovementPlanOut)
def latest_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Your plan for your most recent completed interview."""
    return plan_out(improvement_service.latest_plan(db, user))
