"""
Database bootstrap.

Sprint 0 keeps storage SQLite-first and schema-driven so the repository works
out of the box. Sprint 2 replaces ``schema.sql`` bootstrapping with SQLAlchemy
migrations; this module will then become an engine/session layer only.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger("imad.database")

_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker] = None


def schema_root() -> Path:
    """Absolute path to ``backend/database/schema.sql``."""
    return Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def _normalise_sqlite_url(url: str) -> str:
    """Resolve relative SQLite targets (e.g. ``sqlite:///./imad.db``) to abspaths."""
    if url.startswith("sqlite:///"):
        target = url.replace("sqlite:///", "", 1)
        if target and target != ":memory:" and ":" not in target:
            return f"sqlite:///{Path(target).resolve()}"
    return url


def _build_engine() -> Engine:
    from .config import get_settings

    url = _normalise_sqlite_url(get_settings().DATABASE_URL or "sqlite:///./imad.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def _ensure_schema(engine: Engine) -> None:
    """Idempotently execute ``database/schema.sql`` against a SQLite engine."""
    loc = schema_root()
    if not loc.exists():
        log.warning("schema.sql not found at %s; skipping bootstrap", loc)
        return
    with engine.begin() as conn:
        raw = loc.read_text(encoding="utf-8")
        for statement in raw.split(";\n"):
            cleaned = statement.strip()
            if cleaned and not cleaned.startswith("--"):
                conn.execute(text(cleaned))


def init_db() -> None:
    """Create the global engine/session factory and apply the SQLite schema."""
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        return

    _ENGINE = _build_engine()
    if _ENGINE.dialect.name == "sqlite":
        _ensure_schema(_ENGINE)

    _SESSION_FACTORY = sessionmaker(
        bind=_ENGINE, autoflush=False, autocommit=False, future=True
    )


def get_engine() -> Engine:
    """Lazy accessor for the active engine (initialises on first call)."""
    if _ENGINE is None:
        init_db()
    return _ENGINE


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a scoped ORM session, always closing it."""
    if _SESSION_FACTORY is None:
        init_db()
    db = _SESSION_FACTORY()
    try:
        yield db
    finally:
        db.close()


# Module-level alias kept for offset convenience (typing/ORM).
engine = _ENGINE