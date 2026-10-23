"""Run the real Alembic migrations against a separate PostgreSQL TEST database.

Skipped unless TEST_DATABASE_URL is set (in the environment or backend/.env).
Safety rules, checked before anything runs:
  * the database name must end in "_test";
  * it must not be the same database as DATABASE_URL.
This module downgrades the test database to empty, upgrades it, checks it,
and downgrades it again. It never touches the DATABASE_URL database.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, inspect, make_url, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import BACKEND_DIR, get_settings
from app.db.base import Base
from app.db.session import create_db_engine
from app.models import Answer, Evaluation, InterviewQuestion, InterviewSession, User
from app.models.enums import Difficulty, InterviewType, QuestionType, SessionStatus

pytestmark = pytest.mark.postgres

EXPECTED_TABLES = {
    "alembic_version",
    "users",
    "refresh_tokens",
    "cvs",
    "question_bank",
    "interview_sessions",
    "interview_questions",
    "answers",
    "evaluations",
    "candidate_profiles",  # Milestone 4
    "improvement_plans",  # Milestone 4
    "agent_decisions",  # Milestone 5
}


def _test_database_url() -> str:
    settings = get_settings()
    if settings.test_database_url is None:
        pytest.skip("TEST_DATABASE_URL not set; PostgreSQL migration tests skipped")
    url = settings.test_database_url.get_secret_value()
    test_db = make_url(url)
    if not url.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must be a PostgreSQL URL")
    if not (test_db.database or "").endswith("_test"):
        pytest.fail("Refusing to run: TEST_DATABASE_URL database name must end in '_test'")
    if settings.database_url is not None:
        dev_db = make_url(settings.database_url.get_secret_value())
        same = (test_db.host, test_db.port, test_db.database) == (dev_db.host, dev_db.port, dev_db.database)
        if same:
            pytest.fail("Refusing to run: TEST_DATABASE_URL points at the DATABASE_URL database")
    return url


def _alembic(connection: Connection, *args: str) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    getattr(command, args[0])(config, *args[1:])


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    engine = create_db_engine(_test_database_url())
    with engine.begin() as connection:
        _alembic(connection, "downgrade", "base")  # start from empty
        _alembic(connection, "upgrade", "head")
    yield engine
    with engine.begin() as connection:
        _alembic(connection, "downgrade", "base")  # leave it empty
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine: Engine) -> Iterator[Session]:
    """Session inside a transaction that is always rolled back."""
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()


def test_migration_creates_all_tables_at_head(pg_engine):
    with pg_engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == EXPECTED_TABLES
        current = MigrationContext.configure(connection).get_current_revision()
    head = ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini"))).get_current_head()
    assert current == head


def test_models_and_migrations_are_in_sync(pg_engine):
    """Fails if a model was changed without generating a new migration."""
    with pg_engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_postgres_specific_column_types(pg_engine):
    with pg_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND (table_name, column_name) IN "
                "(('users','id'), ('users','created_at'), ('evaluations','strengths'))"
            )
        ).all()
    types = {(table, column): data_type for table, column, data_type in rows}
    assert types[("users", "id")] == "uuid"
    assert types[("users", "created_at")] == "timestamp with time zone"
    assert types[("evaluations", "strengths")] == "jsonb"


def test_create_read_and_cascade_on_postgres(pg_session):
    user = User(full_name="PG Candidate", email="pg@example.com")
    interview = InterviewSession(
        user=user,
        target_role="Data Scientist",
        interview_type=InterviewType.MIXED,
        difficulty=Difficulty.BEGINNER,
        question_count=1,
        status=SessionStatus.COMPLETED,
        completed_at=datetime.now(UTC),
        overall_score=77,
    )
    question = InterviewQuestion(position=1, text="Why data science?", question_type=QuestionType.BEHAVIORAL)
    question.answer = Answer(answer_text="Because I like data.")
    question.answer.evaluation = Evaluation(score=77, strengths=["Honest"], weaknesses=[])
    interview.questions = [question]
    pg_session.add(interview)
    pg_session.flush()
    pg_session.expire_all()

    loaded = pg_session.get(InterviewSession, interview.id)
    assert loaded.created_at.tzinfo is not None  # timezone-aware on PostgreSQL
    assert loaded.questions[0].answer.evaluation.strengths == ["Honest"]

    pg_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    remaining = pg_session.execute(text("SELECT count(*) FROM evaluations")).scalar_one()
    assert remaining == 0


def test_check_constraint_enforced_on_postgres(pg_session):
    pg_session.add(User(full_name="A", email="a@example.com"))
    pg_session.flush()
    with pytest.raises(IntegrityError):
        pg_session.execute(
            text(
                "INSERT INTO interview_sessions (id, user_id, target_role, interview_type, difficulty,"
                " question_count, status) SELECT gen_random_uuid(), id, 'X', 'technical', 'expert', 5,"
                " 'in_progress' FROM users"
            )
        )
