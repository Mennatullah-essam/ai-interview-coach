"""FastAPI application entry point.

Run from the backend/ folder with:
    uvicorn app.main:app --reload

All product endpoints live under /api/v1 (see API_SPECIFICATION.md).
GET /health and GET /health/db from Milestones 1-2 are kept unchanged.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import auth, cvs, health, interviews, performance, profile, users
from app.core.config import get_settings
from app.core.errors import error_response, install_error_handlers, install_request_id_middleware
from app.db.session import check_database_connection
from app.scoring.similarity import load_engine

SERVICE_NAME = "ai-interview-coach-backend"
APP_VERSION = "0.5.0"
API_PREFIX = "/api/v1"
JSON_BODY_LIMIT = 1024 * 1024  # 1 MB for ordinary JSON requests (spec S-12)

logger = logging.getLogger("app")


def check_production_settings() -> None:
    """Refuse to start in production with unsafe settings (spec 19.0 / 20.6)."""
    settings = get_settings()
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else ""
    if not settings.is_production:
        if "CHANGE_ME" in secret:
            logger.warning("JWT_SECRET still has the placeholder value from .env.example; replace it.")
        return
    problems = []
    if len(secret) < 32 or "CHANGE_ME" in secret:
        problems.append("JWT_SECRET must be set to at least 32 random characters (not the placeholder)")
    if not settings.secure_cookies:
        problems.append("COOKIE_SECURE must not be false (HTTPS is required)")
    if any(origin == "*" for origin in settings.cors_origins):
        problems.append("CORS_ORIGINS must not contain '*'")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=get_settings().log_level.upper())
    check_production_settings()
    load_engine()  # load the similarity model once; never on a request
    yield


app = FastAPI(
    title="AI Interview Coach API",
    description="Backend for the AI Interview Coach project (Milestone 4: candidate profiles, interview intelligence, adaptive interviews, rubric evaluation and improvement plans).",
    version=APP_VERSION,
    lifespan=lifespan,
)

settings = get_settings()
install_error_handlers(app)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Reject oversized requests early, before reading the body."""
    length = request.headers.get("content-length")
    if length and length.isdigit():
        is_cv_upload = request.method == "POST" and request.url.path == f"{API_PREFIX}/cvs"
        limit = get_settings().max_cv_bytes + 64 * 1024 if is_cv_upload else JSON_BODY_LIMIT
        if int(length) > limit:
            if is_cv_upload:
                mb = get_settings().max_cv_bytes // (1024 * 1024)
                return error_response(request, 413, "FILE_TOO_LARGE", f"File is too large. Maximum size is {mb} MB.")
            return error_response(request, 413, "PAYLOAD_TOO_LARGE", "The request is too large.")
    return await call_next(request)


install_request_id_middleware(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # needed for the refresh cookie when the API is on another origin
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-AIC-Client"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

for router in (health.router, auth.router, users.router, cvs.router, profile.router, interviews.router, performance.router):
    app.include_router(router, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the service is running.

    Deliberately does not touch the database, so it keeps answering even
    when PostgreSQL is stopped. Use /health/db to check the database.
    """
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get(
    "/health/db",
    tags=["health"],
    responses={503: {"description": "Database is not reachable or not configured"}},
)
def health_db(response: Response) -> dict[str, str]:
    """Check that the database accepts connections (runs `SELECT 1`)."""
    if check_database_connection():
        return {"status": "healthy", "database": "reachable"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unhealthy", "database": "unreachable"}


# --- built frontend (production) ---------------------------------------------------------------------
# In the Docker image the React build is copied to FRONTEND_DIST and served by this
# same app, so the website and the API share one origin: the refresh cookie stays
# first-party (SameSite=Strict) and no CORS is needed. In local development the
# folder does not exist and nothing below is registered (use `npm run dev`).
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "dist"))
_NOT_FRONTEND = ("api/", "docs", "redoc", "openapi.json", "health")


def mount_frontend(application: FastAPI, dist: Path) -> bool:
    index = dist / "index.html"
    if not index.is_file():
        return False
    root = dist.resolve()
    if (dist / "assets").is_dir():
        # Vite file names contain a content hash, so they can be cached for a long time.
        application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @application.get("/{path:path}", include_in_schema=False)
    def frontend(path: str, request: Request):
        if path.startswith(_NOT_FRONTEND):
            return error_response(request, 404, "NOT_FOUND", "Not found.")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)  # e.g. favicon.svg
        # Every other path is a client-side route (/dashboard, /results, ...): serve the app.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True


if mount_frontend(app, FRONTEND_DIST):
    logger.info("Serving the built frontend from %s", FRONTEND_DIST)
