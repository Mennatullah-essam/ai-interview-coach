"""The single entry point for optional LLM calls.

Guarantees, whatever the caller asks:
* Disabled unless LLM_PROVIDER, LLM_BASE_URL and LLM_MODEL are set.
* A base URL that is not on this machine (localhost) is refused unless
  LLM_ALLOW_EXTERNAL=true, because interview answers would leave the machine
  (API spec D4 and 16.5). The decision is reported by /health, not hidden.
* Only the features listed in LLM_FEATURES may call it.
* Contact details (emails, phone numbers, URLs) are removed from every text
  sent; CV text is never part of a prompt (callers send skill names only).
* The reply must validate against a Pydantic schema, or it is discarded.
* Timeouts and limited retries in the provider; after repeated failures a
  circuit breaker skips the LLM for a cooldown period.
* Every failure returns None with a reason, and the caller uses its
  deterministic fallback. Nothing in the app depends on an LLM answer.
Prompts and replies are never logged (they contain candidate answers).
"""

import logging
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.llm.providers import LLMError, LLMProvider, OpenAICompatibleProvider

logger = logging.getLogger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
_URL = re.compile(r"https?://\S+|www\.\S+")


def minimise(text: str, limit: int = 2000) -> str:
    """Strip contact details and cap the length of text sent to a model."""
    text = _EMAIL.sub("[email]", text or "")
    text = _URL.sub("[link]", text)
    text = _PHONE.sub("[phone]", text)
    return text[:limit]


def is_local_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in _LOCAL_HOSTS or host.endswith(".localhost")


@dataclass
class LLMCallResult:
    value: BaseModel | None
    reason: str  # ok | disabled | feature_off | circuit_open | timeout | rate_limited | ... | schema_invalid
    model: str | None = None
    latency_ms: int | None = None


class LLMGateway:
    def __init__(self, provider: LLMProvider | None, *, status: str, features: set[str],
                 failure_threshold: int = 3, cooldown_seconds: int = 120, external: bool = False):
        self.provider = provider
        self.status = status  # active | disabled | blocked_external | misconfigured
        self.features = features
        self.external = external
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failures = 0
        self._open_until = 0.0
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self.provider is not None and self.status == "active"

    def enabled_for(self, feature: str) -> bool:
        return self.active and feature in self.features

    def describe(self) -> dict:
        return {
            "status": self.status,
            "provider": getattr(self.provider, "name", None) if self.active else None,
            "model": getattr(self.provider, "model", None) if self.active else None,
            "features": sorted(self.features) if self.active else [],
            "external": self.external if self.active else False,
            "circuit_open": time.monotonic() < self._open_until,
        }

    def call(self, feature: str, system: str, user: str, schema: type[BaseModel], *, max_tokens: int = 700) -> LLMCallResult:
        if not self.active:
            return LLMCallResult(None, "disabled")
        if feature not in self.features:
            return LLMCallResult(None, "feature_off")
        if time.monotonic() < self._open_until:
            return LLMCallResult(None, "circuit_open")
        try:
            response = self.provider.complete_json(system, user, max_tokens=max_tokens)
        except LLMError as exc:
            self._record_failure()
            logger.warning("LLM call for %s failed: %s", feature, exc.kind)
            return LLMCallResult(None, exc.kind)
        except Exception as exc:  # never let a provider bug break an interview
            self._record_failure()
            logger.warning("LLM call for %s failed unexpectedly: %s", feature, type(exc).__name__)
            return LLMCallResult(None, "provider_error")
        try:
            value = schema.model_validate(response.data)
        except ValidationError:
            self._record_failure()
            logger.warning("LLM reply for %s did not match the %s schema", feature, schema.__name__)
            return LLMCallResult(None, "schema_invalid", response.model, response.latency_ms)
        with self._lock:
            self._failures = 0
        return LLMCallResult(value, "ok", response.model, response.latency_ms)

    def _record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._open_until = time.monotonic() + self._cooldown
                self._failures = 0
                logger.warning("LLM disabled for %ss after repeated failures", self._cooldown)


_gateway: LLMGateway | None = None
_gateway_lock = threading.Lock()


def build_gateway() -> LLMGateway:
    settings = get_settings()
    features = {f.strip().lower() for f in settings.llm_features if f.strip()}
    if settings.llm_provider == "none":
        return LLMGateway(None, status="disabled", features=features)
    if not settings.llm_base_url or not settings.llm_model:
        logger.warning("LLM_PROVIDER is set but LLM_BASE_URL or LLM_MODEL is missing; the LLM stays off.")
        return LLMGateway(None, status="misconfigured", features=features)
    external = not is_local_url(settings.llm_base_url)
    if external and not settings.llm_allow_external:
        logger.warning("LLM_BASE_URL is not local and LLM_ALLOW_EXTERNAL is false; the LLM stays off.")
        return LLMGateway(None, status="blocked_external", features=features)
    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    provider = OpenAICompatibleProvider(settings.llm_base_url, settings.llm_model, key,
                                        timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
    return LLMGateway(provider, status="active", features=features, failure_threshold=settings.llm_failure_threshold,
                      cooldown_seconds=settings.llm_cooldown_seconds, external=external)


def get_llm() -> LLMGateway:
    global _gateway
    with _gateway_lock:
        if _gateway is None:
            _gateway = build_gateway()
        return _gateway


def set_llm_for_tests(gateway: LLMGateway | None) -> None:
    global _gateway
    with _gateway_lock:
        _gateway = gateway
