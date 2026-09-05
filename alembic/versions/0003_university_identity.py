"""Sprint 3 — university identity & multi-tenant foundation.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

Creates the tenant hierarchy tables:

  universities → faculties → departments → courses → sections
  enrollments (students ↔ sections)

Adds the org-scope foreign keys:

  users.university_id, students.university_id, audit_logs.university_id

Then seeds the default organization (Unilead Academy / ENG / MEC / MEC271 /
section 2026-S1), backfills every tenant-less user/student/audit row into it,
and enrolls every enrolled-nowhere student in the default section — matching
exactly what ``create_all_tables`` + ``bootstrap`` do for fresh SQLite DBs.

Run with::

    cd apps/api
    alembic upgrade head

Local SQLite dev DBs get these columns via ``_migrate_lightweight`` +
``boot_default_organization`` (``app/db/database.py``); Alembic is the
PostgreSQL path.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNIVERSITY = ("UNILEAD", "Unilead Academy", '["university.edu.eg"]')
_FACULTY = ("ENG", "Faculty of Engineering")
_DEPARTMENT = ("MEC", "Mechanical Engineering")
_COURSE = ("MEC271", "Automatic Control", 3)
_SECTION = ("2026-S1", "01")


def upgrade() -> None:
    # --- tenant hierarchy ----------------------------------------------------
    op.create_table(
        "universities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email_domains", sa.Text, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_universities_code", "universities", ["code"])

    op.create_table(
        "faculties",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("university_id", sa.Integer, sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("university_id", "code", name="uq_faculties_university_code"),
    )
    op.create_index("ix_faculties_university_id", "faculties", ["university_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("faculty_id", sa.Integer, sa.ForeignKey("faculties.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("faculty_id", "code", name="uq_departments_faculty_code"),
    )
    op.create_index("ix_departments_faculty_id", "departments", ["faculty_id"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("department_id", sa.Integer, sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("credits", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("department_id", "code", name="uq_courses_department_code"),
    )
    op.create_index("ix_courses_department_id", "courses", ["department_id"])

    op.create_table(
        "sections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("term", sa.String(32), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("instructor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("course_id", "term", "code", name="uq_sections_course_term_code"),
    )
    op.create_index("ix_sections_course_id", "sections", ["course_id"])
    op.create_index("ix_sections_instructor_user_id", "sections", ["instructor_user_id"])

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.String(64), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("section_id", sa.Integer, sa.ForeignKey("sections.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("enrolled_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "section_id", name="uq_enrollments_student_section"),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"])
    op.create_index("ix_enrollments_section_id", "enrollments", ["section_id"])

    # --- org-scope columns ----------------------------------------------------
    op.add_column("users", sa.Column("university_id", sa.Integer, sa.ForeignKey("universities.id"), nullable=True))
    op.create_index("ix_users_university_id", "users", ["university_id"])
    op.add_column("students", sa.Column("university_id", sa.Integer, sa.ForeignKey("universities.id"), nullable=True))
    op.create_index("ix_students_university_id", "students", ["university_id"])
    op.add_column("audit_logs", sa.Column("university_id", sa.Integer, sa.ForeignKey("universities.id"), nullable=True))
    op.create_index("ix_audit_logs_university_id", "audit_logs", ["university_id"])

    # --- seed default org + backfill tenant-less rows (data migration) -------
    bind = op.get_bind()
    auth_result = bind.execute(
        sa.text("SELECT id FROM universities WHERE code = :code"),
        {"code": _UNIVERSITY[0]},
    )
    row = auth_result.fetchone()
    if row is not None:
        university_id = int(row[0])
    else:
        result = bind.execute(
            sa.text(
                "INSERT INTO universities (code, name, email_domains, is_active, created_at) "
                "VALUES (:code, :name, :domains, true, now()) RETURNING id"
            ),
            {"code": _UNIVERSITY[0], "name": _UNIVERSITY[1], "domains": _UNIVERSITY[2]},
        )
        university_id = int(result.fetchone()[0])

        faculty_id = int(
            bind.execute(
                sa.text(
                    "INSERT INTO faculties (university_id, code, name, created_at) "
                    "VALUES (:uid, :code, :name, now()) RETURNING id"
                ),
                {"uid": university_id, "code": _FACULTY[0], "name": _FACULTY[1]},
            ).fetchone()[0]
        )
        department_id = int(
            bind.execute(
                sa.text(
                    "INSERT INTO departments (faculty_id, code, name, created_at) "
                    "VALUES (:fid, :code, :name, now()) RETURNING id"
                ),
                {"fid": faculty_id, "code": _DEPARTMENT[0], "name": _DEPARTMENT[1]},
            ).fetchone()[0]
        )
        course_id = int(
            bind.execute(
                sa.text(
                    "INSERT INTO courses (department_id, code, title, credits, created_at) "
                    "VALUES (:did, :code, :title, :credits, now()) RETURNING id"
                ),
                {
                    "did": department_id,
                    "code": _COURSE[0],
                    "title": _COURSE[1],
                    "credits": _COURSE[2],
                },
            ).fetchone()[0]
        )
        bind.execute(
            sa.text(
                "INSERT INTO sections (course_id, term, code, created_at) "
                "VALUES (:cid, :term, :code, now())"
            ),
            {"cid": course_id, "term": _SECTION[0], "code": _SECTION[1]},
        )

    # Backfill tenant-less accounts / learners / audit rows into the default org.
    bind.execute(
        sa.text("UPDATE users SET university_id = :uid WHERE university_id IS NULL"),
        {"uid": university_id},
    )
    bind.execute(
        sa.text("UPDATE students SET university_id = :uid WHERE university_id IS NULL"),
        {"uid": university_id},
    )
    bind.execute(
        sa.text("UPDATE audit_logs SET university_id = :uid WHERE university_id IS NULL"),
        {"uid": university_id},
    )

    # Enroll every not-yet-enrolled student in the default section so legacy
    # cohorts keep their data visibility through student/instructor endpoints.
    section_row = bind.execute(
        sa.text(
            "SELECT s.id FROM sections s "
            "JOIN courses c ON c.id = s.course_id "
            "JOIN departments d ON d.id = c.department_id "
            "JOIN faculties f ON f.id = d.faculty_id "
            "WHERE f.university_id = :uid ORDER BY s.id LIMIT 1"
        ),
        {"uid": university_id},
    ).fetchone()
    if section_row is not None:
        section_id = int(section_row[0])
        bind.execute(
            sa.text(
                "INSERT INTO enrollments (student_id, section_id, status) "
                "SELECT st.student_id, :sid, 'active' FROM students st "
                "WHERE NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.student_id = st.student_id)"
            ),
            {"sid": section_id},
        )


def downgrade() -> None:
    # Drop the FK columns first: they reference universities, so PostgreSQL
    # refuses to drop that table while these constraints still exist.
    op.drop_index("ix_audit_logs_university_id", table_name="audit_logs")
    op.drop_column("audit_logs", "university_id")
    op.drop_index("ix_students_university_id", table_name="students")
    op.drop_column("students", "university_id")
    op.drop_index("ix_users_university_id", table_name="users")
    op.drop_column("users", "university_id")

    op.drop_table("enrollments")
    op.drop_table("sections")
    op.drop_table("courses")
    op.drop_table("departments")
    op.drop_table("faculties")
    op.drop_table("universities")