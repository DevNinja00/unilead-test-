"""Sprint 2 auth hardening — token lifecycle + password reset + audit log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05

Adds to ``users``:
  - ``token_version``               session/token revocation version marker
  - ``password_reset_*``            hashed, expiring reset code fields
  - ``last_password_change_at``

Creates the ``audit_logs`` table for security-relevant events.

Run with::

    cd apps/api
    alembic upgrade head

Notes
-----
* Mirrors ``Base.metadata.create_all`` output for the new columns/table.
* Local SQLite dev DBs get these columns via ``_migrate_lightweight`` in
  ``app/db/database.py``; Alembic is the PostgreSQL path (batch mode makes
  ``op.add_column`` a no-op there, so the same script is portable).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: token lifecycle + password reset ----------------------------
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("password_reset_code_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("password_reset_sent_at", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("last_password_change_at", sa.DateTime, nullable=True))

    # --- audit_logs -----------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_role", sa.String(16), nullable=False, server_default="'student'"),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(255), nullable=True),
        sa.Column("detail", sa.Text, nullable=False, server_default="''"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="'OK'"),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_column("users", "last_password_change_at")
    op.drop_column("users", "password_reset_sent_at")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_code_hash")
    op.drop_column("users", "token_version")