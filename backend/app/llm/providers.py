"""LLM provider adapters behind one small interface.

Only one adapter is needed: many servers speak the OpenAI chat-completions
protocol, including local ones (Ollama, LM Studio, llama.cpp server, vLLM) and
hosted ones. It uses the standard library (urllib), so no new dependency.

A provider returns the parsed JSON object the model produced. It never decides
anything itself: callers validate the object against a schema and the
application's policy (see gateway.py and intelligence/agent.py).
"""

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """The provider could not produce a usable answer (timeout, HTTP error, bad JSON)."""

    def __init__(self, kind: str, message: str = ""):
        super().__init__(message or kind)
        self.kind = kind  # timeout | rate_limited | http_error | connection | invalid_output


@dataclass
class LLMResponse:
    data: dict
    model: str
    latency_ms: int


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str, *, max_tokens: int = 700) -> LLMResponse: ...


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_object(text: str) -> dict:
    """The first JSON object in a model reply (tolerates code fences and surrounding prose)."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        value = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise LLMError("invalid_output", "no JSON object in the reply") from None
        try:
            value = json.loads(cleaned[start : end + 1])
        except ValueError as exc:
            raise LLMError("invalid_output", "malformed JSON") from exc
    if not isinstance(value, dict):
        raise LLMError("invalid_output", "the reply is not a JSON object")
    return value


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, model: str, api_key: str | None, *, timeout: float = 12.0,
                 max_retries: int = 1, opener=None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._open = opener or urllib.request.urlopen  # injectable for tests

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode("utf-8"),
                                         headers=headers, method="POST")
        with self._open(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def complete_json(self, system: str, user: str, *, max_tokens: int = 700) -> LLMResponse:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        attempt = 0
        while True:
            start = time.perf_counter()
            try:
                raw = self._post(body)
                content = raw["choices"][0]["message"]["content"]
                return LLMResponse(data=parse_json_object(content or ""), model=str(raw.get("model") or self.model),
                                   latency_ms=int((time.perf_counter() - start) * 1000))
            except urllib.error.HTTPError as exc:
                kind = "rate_limited" if exc.code == 429 else "http_error"
                retryable = exc.code == 429 or exc.code >= 500
                wait = 1.0
                if exc.code == 429:
                    try:
                        wait = min(2.0, float(exc.headers.get("Retry-After", "1")))
                    except (TypeError, ValueError):
                        wait = 1.0
                error = LLMError(kind, f"HTTP {exc.code}")
            except (TimeoutError, urllib.error.URLError) as exc:
                timed_out = isinstance(exc, TimeoutError) or "timed out" in str(getattr(exc, "reason", exc))
                error, retryable, wait = LLMError("timeout" if timed_out else "connection", type(exc).__name__), True, 0.5
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                if isinstance(exc, LLMError):
                    raise
                raise LLMError("invalid_output", "unexpected response shape") from exc
            if not retryable or attempt >= self.max_retries:
                raise error
            attempt += 1
            time.sleep(wait)
