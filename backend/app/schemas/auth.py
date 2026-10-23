import re
import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.core.security import normalize_email
from app.schemas.common import StrictModel, Timestamp, Trimmed

# Practical email check: one @, no spaces, a dot in the domain, sane characters.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")


def _valid_email(value: str) -> str:
    value = normalize_email(value)
    if len(value) > 254 or not _EMAIL_RE.match(value) or ".." in value:
        raise ValueError("Please enter a valid email address.")
    return value


Email = Annotated[str, AfterValidator(_valid_email)]


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    created_at: Timestamp


class RegisterIn(StrictModel):
    name: Trimmed = Field(min_length=2, max_length=100)
    email: Email
    password: str = Field(min_length=8, max_length=128)


class LoginIn(StrictModel):
    email: str = Field(min_length=1, max_length=254)  # not format-checked: wrong = invalid credentials
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthOut(TokenOut):
    user: UserOut


class ProfileUpdateIn(StrictModel):
    name: Trimmed | None = Field(default=None, min_length=2, max_length=100)
    email: Email | None = None
