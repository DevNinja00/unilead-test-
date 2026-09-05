"""Copy data from a source DB (typically the dev SQLite file) to PostgreSQL.

The destination schema must already exist — run ``alembic upgrade head``
against the destination first::

    # 1. Create/migrate the destination schema
    DEST_URL=postgresql+psycopg://unilead:pass@localhost:5432/unilead \
        alembic upgrade head

    # 2. Copy every row, preserving primary and foreign keys
    SOURCE_URL=sqlite:///./unilead.db \\
    DEST_URL=postgresql+psycopg://unilead:pass@localhost:5432/unilead \\
        python -m scripts.migrate

The script:
* copies tables in foreign-key dependency order (``users`` first, children
  last), so every ``REFERENCES`` is satisfied when rows are inserted;
* only moves columns that exist in *both* databases (older SQLite files may
  predate the verification columns — they get server defaults on dest);
* keeps the numeric ``id`` values intact so relationships never break;
* coerces integer 0/1 from SQLite into real booleans for PostgreSQL;
* verifies row-per-table counts between source and destination, and exits
  non-zero on any mismatch — safe to put in a release pipeline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from sqlalchemy.types import Boolean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import models  # noqa: E402, F401  (register tables with Base.metadata)
from app.db.database import Base  # noqa: E402


def _engine_from_env(name: str) -> sa.Engine:
    url = os.environ.get(name)
    if not url:
        raise SystemExit(f"Missing {name} env var.")
    return create_engine(url)


def _copy_table(source: sa.Engine, dest: sa.Engine, table: sa.Table) -> int:
    with source.connect() as conn:
        inspector = inspect(conn)
        if table.name not in inspector.get_table_names():
            return 0
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        # Only columns present in BOTH the source and the live model.
        columns = [c for c in table.columns if c.name in existing]
        bool_cols = {c.name for c in columns if isinstance(c.type, Boolean)}
        rows = conn.execute(sa.select(*columns)).mappings().all()

    if not rows:
        return 0

    def _coerce(row: dict) -> dict:
        return {k: (bool(v) if k in bool_cols and v is not None else v) for k, v in row.items()}

    payload = [_coerce(dict(r)) for r in rows]
    with dest.begin() as conn:
        conn.execute(table.insert(), payload)
    return len(payload)


def main() -> int:
    source = _engine_from_env("SOURCE_URL")
    dest = _engine_from_env("DEST_URL")

    with dest.connect() as conn:
        dest_existing = set(inspect(conn).get_table_names())

    moved: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:  # FK dependency order
        if table.name not in dest_existing:
            print(f"SKIP {table.name}: table absent on destination")
            continue
        copied = _copy_table(source, dest, table)
        moved[table.name] = copied
        print(f"ok   {table.name:<28} {copied} rows")

    # Verify per-table row counts.
    mismatched: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in dest_existing:
            continue
        with source.connect() as src, dest.connect() as dst:
            src_count = src.execute(sa.text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar()
            dst_count = dst.execute(sa.text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar()
        if src_count != dst_count:
            mismatched.append(f"{table.name}: source={src_count} dest={dst_count}")

    if mismatched:
        print("\nMISMATCH:\n" + "\n".join(f"  {m}" for m in mismatched))
        return 1

    total = sum(moved.values())
    print(f"\nDone — {total} rows copied, all counts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
