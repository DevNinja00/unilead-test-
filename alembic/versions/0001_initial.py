"""Initial schema — all tables (PostgreSQL-ready).

Revision ID: 0001
Revises:
Create Date: 2026-09-03

Creates all Unilead tables matching the current SQLAlchemy models in
``apps/api/app/db/models.py``. This is the production baseline used by
PostgreSQL. Run with::

    cd apps/api
    alembic upgrade head

Notes
-----
* Mirrors ``Base.metadata.create_all`` output exactly (verified against the
  live models), plus explicit server defaults so raw inserts without the
  ORM still satisfy ``NOT NULL`` constraints.
* String ``server_default`` values are quoted literals — portable across
  SQLite (dev) and PostgreSQL (prod).
* Local SQLite dev DBs are created by ``create_all_tables`` on startup and
  extended by ``_migrate_lightweight`` — Alembic is only required for the
  PostgreSQL production database (see ``app/db/database.py``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users -------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.String(16),
            nullable=False,
            server_default="'student'",
        ),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column(
            "email_verified", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("email_verification_code_hash", sa.String(64), nullable=True),
        sa.Column("email_verification_expires_at", sa.DateTime, nullable=True),
        sa.Column("email_verification_sent_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # --- students -----------------------------------------------------------
    op.create_table(
        "students",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "course_code",
            sa.String(32),
            nullable=False,
            server_default="'MEC271'",
        ),
        sa.Column(
            "course_title",
            sa.String(255),
            nullable=False,
            server_default="'Automatic Control'",
        ),
        sa.Column("overall_progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_students_student_id", "students", ["student_id"], unique=True)

    # --- competency_snapshots ------------------------------------------------
    op.create_table(
        "competency_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("competency_id", sa.String(64), nullable=False),
        sa.Column("competency_name", sa.String(255), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="'not_started'"
        ),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "student_id", "competency_id", name="uq_student_competency"
        ),
    )
    op.create_index(
        "ix_competency_snapshots_student_id", "competency_snapshots", ["student_id"]
    )
    op.create_index(
        "ix_competency_snapshots_competency_id",
        "competency_snapshots",
        ["competency_id"],
    )
    op.create_index(
        "ix_cs_student_status", "competency_snapshots", ["student_id", "status"]
    )

    # --- onboarding_answers ---------------------------------------------------
    op.create_table(
        "onboarding_answers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("learning_challenge", sa.Text, nullable=False),
        sa.Column("preferred_method", sa.Text, nullable=False),
        sa.Column("obstacle", sa.Text, nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_onboarding_answers_student_id", "onboarding_answers", ["student_id"]
    )

    # --- diagnostic_submissions -----------------------------------------------
    op.create_table(
        "diagnostic_submissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column(
            "misconceptions_count", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_diagnostic_submissions_student_id", "diagnostic_submissions", ["student_id"]
    )

    # --- diagnostic_answers ----------------------------------------------------
    op.create_table(
        "diagnostic_answers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "submission_id",
            sa.Integer,
            sa.ForeignKey("diagnostic_submissions.id"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(32), nullable=False),
        sa.Column("competency_id", sa.String(64), nullable=False),
        sa.Column("selected_option_id", sa.String(32), nullable=False),
        sa.Column("correct", sa.Boolean, nullable=False),
        sa.Column("misconception_tag", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_diagnostic_answers_submission_id", "diagnostic_answers", ["submission_id"]
    )

    # --- simulation_runs ---------------------------------------------------------
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("competency_id", sa.String(64), nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False, server_default="'pid-001'"),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("kp", sa.Float, nullable=False),
        sa.Column("ki", sa.Float, nullable=False),
        sa.Column("kd", sa.Float, nullable=False),
        sa.Column("stable", sa.Boolean, nullable=False),
        sa.Column("overshoot", sa.Float, nullable=False),
        sa.Column("settling_time", sa.Float, nullable=False),
        sa.Column("rise_time", sa.Float, nullable=False),
        sa.Column("steady_state_error", sa.Float, nullable=False),
        sa.Column("requirements_met", sa.Boolean, nullable=False),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("misconception", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_simulation_runs_student_id", "simulation_runs", ["student_id"])

    # --- transfer_evaluations ------------------------------------------------------
    op.create_table(
        "transfer_evaluations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("competency_id", sa.String(64), nullable=False),
        sa.Column("scenario_id", sa.String(64), nullable=False),
        sa.Column("response_text", sa.Text, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("matched_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("min_required", sa.Integer, nullable=False, server_default="2"),
        sa.Column("feedback", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_transfer_evaluations_student_id", "transfer_evaluations", ["student_id"]
    )

    # --- remediation_plans ------------------------------------------------------------
    op.create_table(
        "remediation_plans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("competency_id", sa.String(64), nullable=False),
        sa.Column("detected_misconception", sa.String(128), nullable=True),
        sa.Column("recommended_action", sa.String(64), nullable=False),
        sa.Column("conceptual_focus", sa.Text, nullable=False),
        sa.Column("guided_question", sa.Text, nullable=False),
        sa.Column(
            "consecutive_failures", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("total_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("summary_text", sa.Text, nullable=False, server_default="''"),
        sa.Column(
            "remediation_steps_json", sa.Text, nullable=False, server_default="'[]'"
        ),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_remediation_plans_student_id", "remediation_plans", ["student_id"]
    )

    # --- coach_conversations ---------------------------------------------------------
    op.create_table(
        "coach_conversations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column("competency_id", sa.String(64), nullable=True),
        sa.Column(
            "initial_mode", sa.String(32), nullable=False, server_default="'LEARN'"
        ),
        sa.Column("finished", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_coach_conversations_student_id", "coach_conversations", ["student_id"]
    )

    # --- coach_messages ---------------------------------------------------------------
    op.create_table(
        "coach_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.Integer,
            sa.ForeignKey("coach_conversations.id"),
            nullable=False,
        ),
        sa.Column("sender", sa.String(16), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("mode", sa.String(32), nullable=True),
        sa.Column("scaffolding_level", sa.String(16), nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_coach_messages_conversation_id", "coach_messages", ["conversation_id"]
    )

    # --- evidence_events ----------------------------------------------------------------
    op.create_table(
        "evidence_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.String(64),
            sa.ForeignKey("students.student_id"),
            nullable=False,
        ),
        sa.Column(
            "timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("competency_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text, nullable=False),
        sa.Column("result", sa.String(8), nullable=False, server_default="'INFO'"),
    )
    op.create_index("ix_evidence_events_student_id", "evidence_events", ["student_id"])
    op.create_index("ix_evidence_events_timestamp", "evidence_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("evidence_events")
    op.drop_table("coach_messages")
    op.drop_table("coach_conversations")
    op.drop_table("remediation_plans")
    op.drop_table("transfer_evaluations")
    op.drop_table("simulation_runs")
    op.drop_table("diagnostic_answers")
    op.drop_table("diagnostic_submissions")
    op.drop_table("onboarding_answers")
    op.drop_table("competency_snapshots")
    op.drop_table("students")
    op.drop_table("users")
