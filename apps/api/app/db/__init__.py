"""DB package — re-exports the engine, Base, session, and models."""

from .database import (
    Base,
    SessionLocal,
    create_all_tables,
    engine,
    get_db,
    seed_default_students_if_empty,
)
from . import models

__all__ = [
    "Base",
    "SessionLocal",
    "create_all_tables",
    "engine",
    "get_db",
    "seed_default_students_if_empty",
    "models",
]
