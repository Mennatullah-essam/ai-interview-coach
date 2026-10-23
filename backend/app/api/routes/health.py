"""E22 readiness probe. Exposes no secrets, paths or user data."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import check_database_connection, get_session_factory
from app.models import QuestionBankItem
from app.scoring.similarity import engine_status
from app.services.storage import get_storage

router = APIRouter(tags=["health"])


def _question_bank_ok() -> bool:
    try:
        with get_session_factory()() as db:
            count = db.scalar(select(func.count()).select_from(QuestionBankItem).where(QuestionBankItem.is_active.is_(True)))
        return bool(count)
    except Exception:
        return False


@router.get("/health")
def readiness():
    from app.main import APP_VERSION

    database = check_database_connection()
    checks = {
        "database": "ok" if database else "unavailable",
        "models": engine_status(),
        "storage": "ok" if get_storage().is_writable() else "unavailable",
        "question_bank": "ok" if database and _question_bank_ok() else "unavailable",
    }
    ready = all(value in ("ok", "lexical") for value in checks.values())
    body = {"status": "ok" if ready else "unavailable", "version": APP_VERSION, "checks": checks}
    settings = get_settings()
    body["environment"] = settings.app_env
    # Milestone 5: which intelligence is active (informational; does not affect readiness).
    from app.llm.gateway import get_llm

    llm = get_llm().describe()
    body["intelligence"] = {
        "embeddings": "sbert" if checks["models"] == "ok" else ("lexical" if checks["models"] == "lexical" else "unavailable"),
        "llm": llm["status"],
        "llm_features": llm["features"],
    }
    return JSONResponse(body, status_code=200 if ready else 503)
