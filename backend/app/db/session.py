"""Database engine, session factory, FastAPI dependency and connection check.

Nothing here connects to the database at import time. The engine is created
the first time it is needed, so the app (and GET /health) starts even when
PostgreSQL is stopped or DATABASE_URL is not set.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when code needs the database but DATABASE_URL is not set."""


def create_db_engine(url: str, **engine_options) -> Engine:
    connect_args = {}
    if url.startswith("postgresql"):
        # Fail fast instead of hanging when the server is unreachable.
        connect_args["connect_timeout"] = 5
    return create_engine(
        url,
        pool_pre_ping=True,  # drop dead connections before using them
        hide_parameters=True,  # keep query values out of error messages/logs
        connect_args=connect_args,
        **engine_options,
    )


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url
    if database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in."
        )
    return create_db_engine(database_url.get_secret_value())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Usage in a route:  def route(db: Session = Depends(get_db)): ...
    Uncommitted changes are rolled back when the session closes.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection(engine: Engine | None = None) -> bool:
    """Return True if a simple query succeeds; never raises.

    Only the error type is logged, never the connection string or password.
    """
    try:
        engine = engine or get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # any failure means "not reachable"
        logger.warning("Database connection check failed: %s", type(exc).__name__)
        return False
