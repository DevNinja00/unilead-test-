"""Database engine + session factory.

Uses SQLAlchemy 2.0 sync API. The engine is created once at import time
using the ``DATABASE_URL`` env var.

- Default (local dev): SQLite — ``sqlite:///./unilead.db`` (zero-config).
- Production: PostgreSQL — ``postgresql+psycopg://user:pass@host:5432/db``.

Engine tweaks are chosen per dialect: SQLite gets ``check_same_thread=False``
so FastAPI's threadpool can open per-thread connections; PostgreSQL gets
``pool_pre_ping=True`` so stale pooled connections are transparently dropped
and re-established (required for reliability behind a load balancer /
container restarts).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import Settings

_settings = Settings()

# --- Engine ----------------------------------------------------------------
# Normalize the URL: if it's a relative SQLite path, resolve it relative
# to apps/api/ (where uvicorn runs) so the .db file lands next to .env.
DATABASE_URL = _settings.database_url

# Dialect-specific engine options
_connect_args = {}
_engine_options = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    # Allow the FastAPI threadpool to open per-thread connections.
    _connect_args = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql"):
    # Drop & re-establish stale pooled connections (Docker restarts, idle
    # timeouts behind a proxy) instead of surfacing OperationalError.
    _engine_options["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, connect_args=_connect_args, **_engine_options)

# --- Session factory -------------------------------------------------------
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base. All ORM models inherit from this."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a per-request DB session.

    Usage in a router::

        from ..db import get_db
        @router.get("/...")
        def handler(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """Create every table that doesn't yet exist.

    Called once on app startup. For schema changes after the initial
    creation, use Alembic migrations (see ``alembic/`` at the repo root).
    """
    # Import here so all models register with Base.metadata before create.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_lightweight()


_LIGHTWEIGHT_COLUMNS = {
    "users": [
        # (column_name, sqlite_column_definition, default_for_existing_rows)
        ("email_verified", "BOOLEAN NOT NULL DEFAULT 0", "0"),
        ("email_verification_code_hash", "VARCHAR(64)", None),
        ("email_verification_expires_at", "DATETIME", None),
        ("email_verification_sent_at", "DATETIME", None),
    ],
}


def _migrate_lightweight() -> None:
    """Add columns introduced after the initial schema without Alembic.

    SQLite-only helper for the local dev DB. ``Base.metadata.create_all``
    only creates missing *tables* — it never alters existing ones. For the
    small additive schema changes we've made since the first deploy, run
    ``ALTER TABLE ... ADD COLUMN`` for any column that isn't present yet
    (SQLite-safe). Existing rows get the column's default value.

    PostgreSQL is managed exclusively through Alembic (``alembic upgrade
    head``) — see ``alembic/versions/``.
    """
    from sqlalchemy import inspect, text

    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    for table, columns in _LIGHTWEIGHT_COLUMNS.items():
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for col_name, col_def, _default in columns:
            if col_name in existing:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))


def seed_default_students_if_empty() -> None:
    """No-op now — every student is created on signup, with a fresh,
    zero-state competency profile. No demo seeds.

    Kept as a function so callers don't break, but it does nothing.
    """
    return None
