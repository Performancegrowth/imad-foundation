"""
Database bootstrap.

Sprint 0 keeps storage SQLite-first and schema-driven so the repository works
out of the box. Sprint 2 replaces ``schema.sql`` bootstrapping with SQLAlchemy
migrations; this module will then become an engine/session layer only.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger("imad.database")

_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker] = None


def schema_root() -> Path:
    """Locate ``database/schema.sql`` across repo/Docker layouts.

    Walks upward from this module until it finds a ``database/schema.sql``
    sibling. Handles both the local checkout (``backend/app/core/...`` with
    ``database/`` at the repo root) and the Docker layout (``/app/app/core/...``
    with the schema mounted at ``/app/database/schema.sql``).
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / "database" / "schema.sql"
        if candidate.is_file():
            return candidate
    # Fallback to the old Docker convention so the failure is visible.
    return here.parents[2] / "database" / "schema.sql"


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
        # Split on statement terminator tolerating CRLF/LF line endings.
        statements = [s.strip() for s in re.split(r";\r?\n", raw) if s.strip()]
        for statement in statements:
            # Drop full-line comments (header/seed) — inline "-- …" stays valid.
            lines = [ln for ln in statement.splitlines() if not ln.lstrip().startswith("--")]
            cleaned = "\n".join(lines).strip()
            if not cleaned:
                continue
            conn.execute(text(cleaned))
    # Legacy DBs created before the `role` column existed get it backfilled.
    _ensure_users_role(engine)


def _ensure_users_role(engine: Engine) -> None:
    """Idempotently add the ``users.role`` column to older SQLite databases."""
    if engine.dialect.name != "sqlite":
        return
    try:
        cols = {c["name"] for c in engine.execute(text("PRAGMA table_info(users)")).mappings()}
    except Exception:
        return  # users table does not exist yet; fresh schema already has role
    if cols and "role" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'engineer'"))
        log.info("Added users.role column (legacy schema migration).")


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