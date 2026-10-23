"""E05/E06 profile, plus "clear my practice data" (replaces the demo-only E23)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.presenters import user_out
from app.core.errors import AppError
from app.db.session import get_db
from app.models import User
from app.schemas.auth import ProfileUpdateIn, UserOut
from app.services import interview_service
from app.services.storage import get_storage

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.name is None and body.email is None:
        raise AppError("VALIDATION_ERROR", "Nothing to update.", 422)
    if body.email is not None and body.email != user.email:
        taken = db.scalar(select(User.id).where(User.email == body.email, User.id != user.id))
        if taken is not None:
            raise AppError("EMAIL_ALREADY_IN_USE", "Another account already uses this email.", 409)
        user.email = body.email
    if body.name is not None:
        user.full_name = body.name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("EMAIL_ALREADY_IN_USE", "Another account already uses this email.", 409) from exc
    db.refresh(user)
    return user_out(user)


@router.delete("/me/data")
def clear_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete the signed-in user's CVs (and files) and interviews. The account stays.

    This is the authenticated replacement for the spec's demo-only E23 reset:
    it only ever touches the caller's own data.
    """
    cvs, interviews, keys = interview_service.reset_user_data(db, user)
    storage = get_storage()
    for key in keys:  # files are removed after the database commit
        storage.delete(key)
    return {"reset": True, "deleted": {"cvs": cvs, "interviews": interviews}}
