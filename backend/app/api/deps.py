"""Shared FastAPI dependencies.

`get_current_user` is the ONLY way endpoints learn who is calling (spec 5.2):
it reads `Authorization: Bearer <access token>`, validates the JWT and loads
the user. Endpoints never take a user id from the request.
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)

CLIENT_HEADER = "X-AIC-Client"


def _unauthorized(code: str = "UNAUTHORIZED") -> AppError:
    message = "Your session has expired. Please log in again." if code == "TOKEN_EXPIRED" else "Please log in to continue."
    return AppError(code, message, 401, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized(exc.code) from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_client_header(request: Request) -> None:
    """CSRF defence for the cookie-authenticated routes (refresh, logout).

    Browsers only let another site send a custom header after a CORS pre-flight,
    which our CORS allow-list refuses, so a forged cross-site request fails here.
    """
    if not request.headers.get(CLIENT_HEADER):
        raise AppError("FORBIDDEN", "Missing client header.", 403)
