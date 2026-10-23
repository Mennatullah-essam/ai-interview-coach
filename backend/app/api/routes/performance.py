"""E20/E21: skill scores and dashboard summary, computed from stored results."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.interviews import SkillsOut, SummaryOut
from app.services import interview_service as svc

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/skills", response_model=SkillsOut)
def skills(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mean of each skill over completed interviews, highest first. Empty for new users."""
    items, counted = svc.skill_scores(db, user)
    return SkillsOut(skills=items, interviews_counted=counted)


@router.get("/summary", response_model=SummaryOut)
def summary(
    trend_limit: int = Query(12, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return SummaryOut(**svc.summary(db, user, trend_limit))
