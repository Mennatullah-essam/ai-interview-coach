"""E07-E10: upload, list, read and delete the signed-in user's CVs."""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.api.deps import get_current_user
from app.api.presenters import cv_detail_out, cv_out
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import CV, User
from app.models.enums import CVFileType, CVStatus
from app.schemas.interviews import CVDetailOut, CVPage
from app.services import interview_service, profile_service
from app.services.cv_parsing import EXTRACTOR_VERSION, parse_cv, sanitize_filename
from app.services.storage import get_storage

router = APIRouter(prefix="/cvs", tags=["cvs"])
logger = logging.getLogger(__name__)


def _too_large() -> AppError:
    mb = get_settings().max_cv_bytes // (1024 * 1024)
    return AppError("FILE_TOO_LARGE", f"File is too large. Maximum size is {mb} MB.", 413)


def _store_cv(db: Session, user: User, data: bytes, filename: str) -> CV:
    parsed = parse_cv(data, filename)  # raises UNSUPPORTED_FILE_TYPE / CV_UNREADABLE
    storage = get_storage()
    key = storage.save(data, parsed.extension)
    cv = CV(
        user_id=user.id,
        original_filename=sanitize_filename(filename),
        storage_path=key,
        file_type=CVFileType(parsed.extension),
        file_size_bytes=len(data),
        sha256=parsed.sha256,
        status=CVStatus.PARSED,
        extracted_text=parsed.text,
        skills=parsed.skills,
        experience=parsed.experience,
        education=parsed.education,
        projects=parsed.projects,
        extractor_version=EXTRACTOR_VERSION,
    )
    db.add(cv)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)  # never leave an orphaned file behind
        raise
    db.refresh(cv)
    # Milestone 4: (re)build the draft candidate profile from the new CV. A failure
    # here must never lose the upload, so it is logged and the profile can be rebuilt later.
    try:
        profile_service.refresh_from_cv(db, user, cv)
    except Exception:
        logger.exception("Profile extraction failed for CV %s", cv.id)
        db.rollback()
    return cv


@router.post(
    "",
    response_model=CVDetailOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"],
                "properties": {"file": {"type": "string", "format": "binary"}},
            }}},
        }
    },
)
async def upload_cv(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Upload a PDF or DOCX CV (multipart field `file`, max 5 MB)."""
    max_bytes = get_settings().max_cv_bytes
    try:
        form = await request.form(max_files=1, max_fields=0)
    except Exception as exc:  # malformed multipart or extra parts
        raise AppError("VALIDATION_ERROR", "Send exactly one file in a field named 'file'.", 422) from exc
    upload = form.get("file")
    if list(form.keys()) != ["file"] or not isinstance(upload, UploadFile):
        raise AppError("VALIDATION_ERROR", "Send exactly one file in a field named 'file'.", 422)
    data = await upload.read(max_bytes + 1)
    await form.close()
    if len(data) > max_bytes:
        raise _too_large()
    if not data:
        raise AppError("CV_UNREADABLE", "The uploaded file is empty.", 422)
    cv = await run_in_threadpool(_store_cv, db, user, data, upload.filename or "")
    return cv_detail_out(cv)


@router.get("", response_model=CVPage)
def list_cvs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(CV).where(CV.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(CV.created_at.desc(), CV.id).limit(limit).offset(offset))
    return CVPage(items=[cv_out(cv) for cv in items], total=total, limit=limit, offset=offset)


@router.get("/{cv_id}", response_model=CVDetailOut)
def get_cv(cv_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cv_detail_out(interview_service.get_owned_cv(db, user, cv_id))


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv(cv_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete the CV, its extracted data and its file. Interviews that used it are kept."""
    cv = interview_service.get_owned_cv(db, user, cv_id)
    key = cv.storage_path
    db.delete(cv)
    db.commit()
    get_storage().delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
