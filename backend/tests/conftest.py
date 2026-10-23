"""Shared test fixtures.

Safety: API and model tests use a throwaway in-memory SQLite database and a
temporary folder for CV files, so they never touch your PostgreSQL data or
your real storage folder. Tables are created with create_all() HERE ONLY,
for speed; the real app relies on Alembic migrations, which are tested
against a separate PostgreSQL *_test database in test_migrations_postgres.py.
"""

import os
from collections.abc import Iterator

# Test settings must be in place before the app is imported.
os.environ["APP_ENV"] = "test"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
os.environ["PASSWORD_HASH_COST"] = "10"  # fast hashing in tests only
os.environ["JWT_SECRET"] = "test-only-secret-0123456789-abcdefghijklmnop"
os.environ["SIMILARITY_BACKEND"] = "lexical"
os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "1000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (register all models)
from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.services.question_bank import load_bank_file, seed_bank  # noqa: E402

get_settings.cache_clear()

PASSWORD = "correct-horse-battery-9"
CLIENT_HEADER = {"X-AIC-Client": "web"}


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    # SQLite ignores foreign keys (and ON DELETE rules) unless this is on.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,  # one shared connection, so the in-memory DB persists
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def sqlite_engine() -> Iterator[Engine]:
    engine = make_sqlite_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _isolated_storage_and_limits(tmp_path, monkeypatch):
    """Every test gets its own CV folder and a fresh rate limiter."""
    monkeypatch.setenv("CV_STORAGE_DIR", str(tmp_path / "cvs"))
    get_settings.cache_clear()
    reset_rate_limits()
    yield
    get_settings.cache_clear()


# --- API fixtures ----------------------------------------------------------------------


@pytest.fixture
def api_session_factory(sqlite_engine: Engine):
    factory = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)
    entries, note = load_bank_file(get_settings().question_bank_path)
    with factory() as db:
        seed_bank(db, entries, note)
    return factory


@pytest.fixture
def client(api_session_factory) -> Iterator[TestClient]:
    from app.main import app

    def override_get_db():
        session = api_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str, name: str = "Test User", password: str = PASSWORD):
    response = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": password})
    assert response.status_code == 201, response.text
    return response


def auth_headers(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


REFRESH_COOKIE = "aic_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def present_refresh_cookie(client: TestClient, value: str) -> None:
    """Make `value` the ONLY refresh cookie the client will send on its next request.

    Simulates a browser (or an attacker) presenting a specific, possibly old, token.

    Do not use a bare `client.cookies.set(...)` for this. The cookie the server set
    sits in the jar under the host's effective domain (e.g. "testserver.local"),
    while `set()` without a domain stores domain="", a different jar key. Both
    cookies are then sent (`Cookie: aic_refresh=<injected>; aic_refresh=<current>`)
    and Starlette keeps the LAST duplicate, so the server would silently receive the
    current, valid token instead of the one the test meant to present.
    """
    client.cookies.delete(REFRESH_COOKIE)  # every domain and path
    client.cookies.set(REFRESH_COOKIE, value, path=REFRESH_COOKIE_PATH)
    in_jar = [cookie for cookie in client.cookies.jar if cookie.name == REFRESH_COOKIE]
    assert len(in_jar) == 1, f"expected exactly one {REFRESH_COOKIE} cookie, found {len(in_jar)}"


@pytest.fixture
def user_a(client):
    return auth_headers(register(client, "alice@example.com", "Alice Anders"))


@pytest.fixture
def user_b(client):
    return auth_headers(register(client, "bob@example.com", "Bob Brown"))
