"""Settings, engine/session creation and the connection check."""

import logging

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

import app.db.session as session_module
from app.core.config import Settings
from app.db.session import (
    DatabaseNotConfiguredError,
    check_database_connection,
    create_db_engine,
    get_db,
)

FAKE_PASSWORD = "not-a-real-password-123"
UNREACHABLE_URL = f"postgresql+psycopg://someone:{FAKE_PASSWORD}@127.0.0.1:1/nowhere"


@pytest.fixture(autouse=True)
def clear_cached_engine():
    # Keep references: tests may monkeypatch these module attributes.
    cached = (session_module.get_engine, session_module.get_session_factory)
    for fn in cached:
        fn.cache_clear()
    yield
    for fn in cached:
        fn.cache_clear()


def test_settings_read_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_URL)

    settings = Settings(_env_file=None)

    assert settings.database_url.get_secret_value() == UNREACHABLE_URL
    # The password must not leak if settings are printed or logged.
    assert FAKE_PASSWORD not in repr(settings)
    assert FAKE_PASSWORD not in str(settings)


def test_settings_database_url_is_optional(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert Settings(_env_file=None).database_url is None


def test_get_engine_without_database_url_raises_clear_error(monkeypatch):
    monkeypatch.setattr(session_module, "get_settings", lambda: Settings(_env_file=None, database_url=None))

    with pytest.raises(DatabaseNotConfiguredError, match="DATABASE_URL is not set"):
        session_module.get_engine()


def test_postgres_engine_uses_psycopg_and_hides_password():
    engine = create_db_engine(UNREACHABLE_URL)  # creating an engine does not connect

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert FAKE_PASSWORD not in repr(engine)
    assert FAKE_PASSWORD not in str(engine.url)
    engine.dispose()


def test_get_db_yields_a_working_session_and_closes_it(monkeypatch, sqlite_engine):
    factory = sessionmaker(bind=sqlite_engine)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)

    generator = get_db()
    session = next(generator)
    assert isinstance(session, Session)
    assert session.execute(text("SELECT 1")).scalar_one() == 1

    with pytest.raises(StopIteration):
        next(generator)  # runs the `finally: session.close()` block
    assert not session.in_transaction()


def test_connection_check_succeeds_for_working_database(sqlite_engine):
    assert check_database_connection(sqlite_engine) is True


def test_connection_check_fails_safely_without_leaking_password(caplog):
    engine = create_db_engine(UNREACHABLE_URL)

    with caplog.at_level(logging.WARNING):
        assert check_database_connection(engine) is False

    assert "Database connection check failed" in caplog.text
    assert FAKE_PASSWORD not in caplog.text
    engine.dispose()


def test_connection_check_returns_false_when_not_configured(monkeypatch):
    monkeypatch.setattr(session_module, "get_settings", lambda: Settings(_env_file=None, database_url=None))

    assert check_database_connection() is False
