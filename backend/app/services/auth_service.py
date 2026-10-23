"""Registration, login, refresh-token rotation and logout.

Session model (API spec 5.4, "Phase 2"):
* access token: short-lived JWT, returned in the JSON body, kept in memory by
  the frontend and sent as `Authorization: Bearer ...`;
* refresh token: random value in an HttpOnly cookie, stored only as a SHA-256
  hash in refresh_tokens, rotated on every use and revoked on logout.
If a refresh token that was already rotated is presented again (after a short
grace period for simultaneous tabs), every session of that user is revoked
(likely token theft).
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import (
    burn_password_check,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    normalize_email,
    refresh_token_expiry,
    verify_password,
)
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)

# Two tabs reloading at the same moment both present the same refresh cookie.
# A token rotated this recently is treated as a benign race, not as theft.
REUSE_GRACE_SECONDS = 20


def invalid_credentials() -> AppError:
    return AppError("INVALID_CREDENTIALS", "Incorrect email or password.", 401)


def token_invalid() -> AppError:
    return AppError("TOKEN_INVALID", "Your session has ended. Please log in again.", 401)


def email_taken(code: str = "EMAIL_ALREADY_REGISTERED") -> AppError:
    return AppError(code, "An account with this email already exists.", 409)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def register(db: Session, *, name: str, email: str, password: str) -> User:
    if find_user_by_email(db, email) is not None:
        raise email_taken()
    user = User(full_name=name, email=normalize_email(email), password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:  # two registrations racing for the same email
        db.rollback()
        raise email_taken() from exc
    logger.info("User registered: %s", user.id)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = find_user_by_email(db, email)
    if user is None or not user.password_hash:
        burn_password_check(password)  # same timing whether or not the email exists
        raise invalid_credentials()
    if not verify_password(password, user.password_hash) or not user.is_active:
        raise invalid_credentials()
    return user


def start_session(db: Session, user: User) -> str:
    """Create a refresh-token row and return the raw token for the cookie."""
    raw, token_hash = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=refresh_token_expiry()))
    db.flush()
    return raw


def rotate_session(db: Session, raw_token: str | None) -> tuple[User, str]:
    if not raw_token:
        raise token_invalid()
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    if record is None:
        raise token_invalid()
    if record.revoked_at is not None and _aware(record.revoked_at) > _now() - timedelta(seconds=REUSE_GRACE_SECONDS):
        user = db.get(User, record.user_id)
        if user is None or not user.is_active or _aware(record.expires_at) <= _now():
            raise token_invalid()
        return user, start_session(db, user)
    if record.revoked_at is not None:
        # An older rotated token was reused: likely theft, so revoke every session.
        logger.warning("Refresh token reuse detected for user %s; revoking all sessions", record.user_id)
        revoke_all_sessions(db, record.user_id)
        db.commit()
        raise token_invalid()
    if _aware(record.expires_at) <= _now():
        raise token_invalid()
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise token_invalid()
    record.revoked_at = _now()
    new_raw = start_session(db, user)
    return user, new_raw


def end_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    if record is not None and record.revoked_at is None:
        record.revoked_at = _now()


def revoke_all_sessions(db: Session, user_id) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
