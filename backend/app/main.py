"""FastAPI application entry point.

Run from the backend/ folder with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

SERVICE_NAME = "ai-interview-coach-backend"
APP_VERSION = "0.1.0"

app = FastAPI(
    title="AI Interview Coach API",
    description="Backend for the AI Interview Coach project (Milestone 1: foundation).",
    version=APP_VERSION,
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the service is running.

    Used by developers, tests and, later, deployment health checks.
    It does not check any external services yet (there are none).
    """
    return {"status": "healthy", "service": SERVICE_NAME}
