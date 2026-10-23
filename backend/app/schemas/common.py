from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite returns naive datetimes; they are stored as UTC
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ISO-8601 UTC with a trailing Z, as required by the API spec (4.1).
Timestamp = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]


# Strings that are trimmed before length checks (names, roles). Passwords are NOT trimmed.
Trimmed = Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v)]


class StrictModel(BaseModel):
    """Request bodies reject unknown fields (spec S-12)."""

    model_config = ConfigDict(extra="forbid")
