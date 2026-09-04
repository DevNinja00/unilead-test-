"""Database engine + session factory.

Uses SQLAlchemy 2.0 sync API with SQLite by default. The engine is created
once at import time using the ``DATABASE_URL`` env var (default:
``sqlite:///./unilead.db``).

For SQLite, we enable ``check_same_thread=False`` so FastAPI's threadpool
can use the same connection safely (SQLite connections are not actually
shared — each thread gets its own via the session factory).
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

# SQLite-specific tweaks
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

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


def seed_default_students_if_empty() -> None:
    """No-op now — every student is created on signup, with a fresh,
    zero-state competency profile. No demo seeds.

    Kept as a function so callers don't break, but it does nothing.
    """
    return None
