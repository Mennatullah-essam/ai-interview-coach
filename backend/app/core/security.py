"""Password hashing, access tokens (JWT) and refresh tokens.

Passwords: scrypt from Python's standard library (memory-hard, salted, listed
by OWASP alongside argon2id and bcrypt). Stored as one self-describing string:
    scrypt$<log2 N>$<r>$<p>$<salt b64>$<hash b64>
so the cost can be raised later without breaking existing hashes.

Access tokens: short-lived HS256 JWTs (sub = user id, typ = "access").
Refresh tokens: random opaque strings; only their SHA-256 hash is stored.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SCRYPT_R = 8
_SCRYPT_P = 1
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER = "ai-interview-coach"


# --- passwords -------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _scrypt(password: str, salt: bytes, log_n: int, r: int, p: int) -> bytes:
    n = 2**log_n
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
        maxmem=128 * r * (n + p + 2) + 1024 * 1024, dklen=32,
    )


def hash_password(password: str) -> str:
    log_n = get_settings().password_hash_cost
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, log_n, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${log_n}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check. Returns False for missing or malformed hashes."""
    if not stored:
        return False
    try:
        scheme, log_n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        actual = _scrypt(password, base64.b64decode(salt_b64), int(log_n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


@lru_cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check, so unknown emails can't be detected by timing."""
    verify_password(password, _dummy_hash())


# --- access tokens -----------------------------------------------------------


@lru_cache
def _jwt_secret() -> str:
    settings = get_settings()
    if settings.jwt_secret is not None:
        return settings.jwt_secret.get_secret_value()
    if settings.is_production:
        raise RuntimeError("JWT_SECRET must be set when APP_ENV=production.")
    # Development convenience: a random per-process secret. Access tokens then
    # stop working after a restart, but the refresh cookie silently renews them.
    logger.warning("JWT_SECRET is not set; using a temporary secret for this process.")
    return secrets.token_urlsafe(48)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Return (token, lifetime in seconds)."""
    minutes = get_settings().access_token_minutes
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iss": _JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGORITHM), minutes * 60


class TokenError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code  # TOKEN_EXPIRED or UNAUTHORIZED


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[_JWT_ALGORITHM],  # never accept "none" or another algorithm
            issuer=_JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "typ", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("UNAUTHORIZED") from exc
    if payload.get("typ") != "access":
        raise TokenError("UNAUTHORIZED")
    try:
        return uuid.UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise TokenError("UNAUTHORIZED") from exc


# --- refresh tokens ----------------------------------------------------------


def new_refresh_token() -> tuple[str, str]:
    """Return (raw token for the cookie, SHA-256 hash for the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days)


# --- emails ------------------------------------------------------------------


def normalize_email(email: str) -> str:
    return email.strip().lower()
