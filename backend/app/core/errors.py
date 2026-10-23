"""Uniform error envelope (API spec section 18) and request ids.

Every failure response looks like:
    {"error": {"code": "...", "message": "...", "details": [], "retryable": false,
               "request_id": "req_..."}}
Messages are safe to show to users: no stack traces, SQL, file paths or secrets.
"""

import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, InterfaceError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """An expected error with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        details: list | None = None,
        retryable: bool = False,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.retryable = retryable
        self.headers = headers


def not_found(code: str, what: str) -> AppError:
    return AppError(code, f"{what} not found.", 404)


def new_request_id() -> str:
    return f"req_{secrets.token_hex(4)}"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or new_request_id()


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: list | None = None,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "retryable": retryable,
            "request_id": request_id,
        }
    }
    all_headers = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(status_code=status_code, content=body, headers=all_headers)


# Validation failures on these routes get a more specific code than VALIDATION_ERROR.
_ROUTE_VALIDATION_CODES = {
    ("POST", "/api/v1/interviews"): ("INVALID_INTERVIEW_CONFIG", "Please check the interview settings."),
}

_FRIENDLY_ISSUES = {
    "missing": "is required",
    "string_too_short": "is too short",
    "string_too_long": "is too long",
    "value_error": "is not valid",
    "enum": "has an unsupported value",
    "literal_error": "has an unsupported value",
    "uuid_parsing": "is not a valid id",
    "int_parsing": "must be a whole number",
    "extra_forbidden": "is not allowed",
}


def _validation_details(exc: RequestValidationError) -> list[dict]:
    details = []
    for err in exc.errors():
        location = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
        detail = {"field": ".".join(location) or "request", "issue": err.get("type", "invalid")}
        ctx = err.get("ctx") or {}
        for key in ("min_length", "max_length", "ge", "le"):
            if key in ctx:
                detail["limit"] = ctx[key]
        details.append(detail)
    return details


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return error_response(
            request, exc.status_code, exc.code, exc.message,
            details=exc.details, retryable=exc.retryable, headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        details = _validation_details(exc)
        code, message = _ROUTE_VALIDATION_CODES.get(
            (request.method, request.url.path), ("VALIDATION_ERROR", None)
        )
        if message is None:
            first = details[0] if details else {"field": "request", "issue": "invalid"}
            issue = _FRIENDLY_ISSUES.get(first["issue"], "is not valid")
            field = first["field"].replace("_", " ")
            message = f"The {field} field {issue}." if first["field"] != "request" else "The request is not valid."
        return error_response(request, 422, code, message, details=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "UNAUTHORIZED", 403: "FORBIDDEN"}
        code = codes.get(exc.status_code, "HTTP_ERROR")
        message = {404: "Not found.", 405: "Method not allowed."}.get(exc.status_code, str(exc.detail))
        return error_response(request, exc.status_code, code, message, headers=getattr(exc, "headers", None))

    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def handle_db_down(request: Request, exc: Exception):
        logger.warning("Database error: %s", type(exc).__name__)
        return error_response(
            request, 503, "DATABASE_UNAVAILABLE",
            "The database is temporarily unavailable. Please try again.", retryable=True,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error (request_id=%s)", _request_id(request))
        return error_response(request, 500, "INTERNAL_ERROR", "Something went wrong. Please try again.")


def install_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = new_request_id()
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request.state.request_id)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response
