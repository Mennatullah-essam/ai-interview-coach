"""Small in-memory rate limiter for the login and registration endpoints.

It keeps a sliding one-minute window per (action, client IP). Because it lives
in process memory it resets on restart and is per-process; that is enough for
local development and a single server. A multi-server deployment would need a
shared store (e.g. Redis) instead.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

_WINDOW_SECONDS = 60.0
_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request, action: str) -> None:
    limit = get_settings().auth_rate_limit_per_minute
    key = (action, _client_ip(request))
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] > _WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - hits[0])) + 1)
            raise AppError(
                "RATE_LIMITED",
                "Too many attempts. Please wait a minute and try again.",
                429,
                retryable=True,
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


def reset_rate_limits() -> None:
    """Used by tests."""
    with _lock:
        _hits.clear()
