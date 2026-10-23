"""E01-E04: register, login, refresh, logout.

The refresh token travels only in an HttpOnly cookie scoped to /api/v1/auth,
so page JavaScript can never read it. Refresh and logout additionally require
the X-AIC-Client header (CSRF defence, see deps.require_client_header).
"""

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_client_header
from app.api.presenters import user_out
from app.core.config import get_settings
from app.core.errors import AppError, error_response
from app.core.rate_limit import check_rate_limit
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import AuthOut, LoginIn, RegisterIn
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "aic_refresh"
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.refresh_token_days * 24 * 3600,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE, path=COOKIE_PATH, httponly=True, secure=settings.secure_cookies, samesite="strict"
    )


def _auth_response(response: Response, user, raw_refresh: str) -> AuthOut:
    token, expires_in = create_access_token(user.id)
    _set_refresh_cookie(response, raw_refresh)
    response.headers["Cache-Control"] = "no-store"
    return AuthOut(user=user_out(user), access_token=token, expires_in=expires_in)


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate_limit(request, "register")
    user = auth_service.register(db, name=body.name, email=body.email, password=body.password)
    raw = auth_service.start_session(db, user)
    db.commit()
    db.refresh(user)
    return _auth_response(response, user, raw)


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate_limit(request, "login")
    user = auth_service.authenticate(db, email=body.email, password=body.password)
    raw = auth_service.start_session(db, user)
    db.commit()
    return _auth_response(response, user, raw)


@router.post(
    "/refresh",
    response_model=AuthOut,
    dependencies=[Depends(require_client_header)],
    responses={401: {"description": "TOKEN_INVALID: no valid session; the cookie is cleared"}},
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    aic_refresh: str | None = Cookie(default=None),
):
    """Rotate the refresh cookie and return a new access token plus the user.

    The frontend calls this on page load to restore the session after a reload.
    """
    try:
        user, raw = auth_service.rotate_session(db, aic_refresh)
    except AppError as exc:
        failed = error_response(request, exc.status_code, exc.code, exc.message)
        _clear_refresh_cookie(failed)
        return failed
    db.commit()
    return _auth_response(response, user, raw)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_client_header)])
def logout(db: Session = Depends(get_db), aic_refresh: str | None = Cookie(default=None)):
    """Revoke the current session and clear the cookie. Always succeeds."""
    auth_service.end_session(db, aic_refresh)
    db.commit()
    done = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(done)
    return done
