"""Alembic environment: connects Alembic to our settings and models.

The database URL comes from DATABASE_URL (environment variable or
backend/.env) via app.core.config. It is never written to alembic.ini.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_db_engine

config = context.config

if config.config_file_name is not None:
    # Keep the app's own loggers working when migrations run inside tests.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_database_url() -> str:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env in the backend "
            "folder and fill in your PostgreSQL connection string."
        )
    return database_url.get_secret_value()


def configure_and_run(**kwargs) -> None:
    context.configure(target_metadata=target_metadata, compare_type=True, **kwargs)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print SQL instead of running it."""
    configure_and_run(
        url=get_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )


def run_with_connection(connection: Connection) -> None:
    configure_and_run(connection=connection)


def run_migrations_online() -> None:
    # Tests can hand Alembic an existing connection instead of a URL.
    connection = config.attributes.get("connection")
    if connection is not None:
        run_with_connection(connection)
        return

    # NullPool: no connection pooling needed for a one-off command.
    engine = create_db_engine(get_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            run_with_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
