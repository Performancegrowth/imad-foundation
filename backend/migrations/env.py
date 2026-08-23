"""Alembic migration environment for the Imad backend.

Reads the SQLAlchemy URL from the ``DATABASE_URL`` environment variable at
runtime (falling back to the SQLite development URL) and registers the
application model package so schema metadata can be discovered.

Note: model classes in ``app.models`` are Pydantic contracts today; the
SQLAlchemy declarative ``Base.metadata`` arrives with ORM adoption, at which
point ``target_metadata`` is wired to it here.
"""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from logging.config import fileConfig

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Register application models (safe: pure-Pydantic, no side-effect DB I/O).
import app.models  # noqa: F401, E402

_database_url = os.getenv("DATABASE_URL", "sqlite:///./imad.db")
config.set_main_option("sqlalchemy.url", _database_url)

# Pydantic-only today; set once SQLAlchemy ORM models are added.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generate SQL)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB engine."""
    connectable = create_engine(_database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()