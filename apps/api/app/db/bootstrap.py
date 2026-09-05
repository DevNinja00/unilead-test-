"""Idempotent default-organization bootstrap (Sprint 3).

The platform ships with one seeded tenant — the "Unilead Academy" default
organization — so that existing accounts and the untouched frontend keep
working while universities are being provisioned. Any user/student with a
``NULL`` ``university_id`` is backfilled into it; new signups without a
tenant get auto-enrolled in its default section.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from . import crud
from .models import Department, Faculty, Section, Student, University, User

_log = logging.getLogger("unilead.bootstrap")

# ---------------------------------------------------------------------------
# Default organization seed (one faculty / one department / one course / one
# section, mirroring the legacy MEC271 cohort).
# ---------------------------------------------------------------------------

DEFAULT_UNIVERSITY = {
    "code": "UNILEAD",
    "name": "Unilead Academy",
    "email_domains": ["university.edu.eg"],
}

DEFAULT_ORG = {
    "faculties": [
        {
            "code": "ENG",
            "name": "Faculty of Engineering",
            "departments": [
                {
                    "code": "MEC",
                    "name": "Mechanical Engineering",
                    "courses": [
                        {
                            "code": "MEC271",
                            "title": "Automatic Control",
                            "credits": 3,
                            "sections": [{"term": "2026-S1", "code": "01"}],
                        }
                    ],
                }
            ],
        }
    ]
}


def ensure_default_organization(db: Session) -> University:
    """Idempotently create the default university + org tree.

    Returns the default ``University`` row. Safe to call on every start /
    app import — uses get-or-create semantics throughout.
    """
    university = crud.get_university_by_code(db, DEFAULT_UNIVERSITY["code"])
    if university is None:
        university = crud.create_university(
            db,
            code=DEFAULT_UNIVERSITY["code"],
            name=DEFAULT_UNIVERSITY["name"],
            email_domains=DEFAULT_UNIVERSITY["email_domains"],
        )
        _log.info("created default university %s", university.code)

    branch = DEFAULT_ORG["faculties"][0]
    faculty = (
        db.query(Faculty)
        .filter(Faculty.university_id == university.id, Faculty.code == branch["code"])
        .first()
    )
    if faculty is None:
        faculty = crud.create_faculty(
            db, university_id=university.id, code=branch["code"], name=branch["name"]
        )

    dept_branch = branch["departments"][0]
    department = (
        db.query(Department)
        .filter(Department.faculty_id == faculty.id, Department.code == dept_branch["code"])
        .first()
    )
    if department is None:
        department = crud.create_department(
            db, faculty_id=faculty.id, code=dept_branch["code"], name=dept_branch["name"]
        )

    course_branch = dept_branch["courses"][0]
    course = (
        db.query(crud.models.Course)
        .filter(
            crud.models.Course.department_id == department.id,
            crud.models.Course.code == course_branch["code"],
        )
        .first()
    )
    if course is None:
        course = crud.create_course(
            db,
            department_id=department.id,
            code=course_branch["code"],
            title=course_branch["title"],
            credits=course_branch["credits"],
        )

    section_branch = course_branch["sections"][0]
    section = (
        db.query(Section)
        .filter(
            Section.course_id == course.id,
            Section.term == section_branch["term"],
            Section.code == section_branch["code"],
        )
        .first()
    )
    if section is None:
        section = crud.create_section(
            db, course_id=course.id, term=section_branch["term"], code=section_branch["code"]
        )

    db.commit()
    return university


def get_default_section_id(db: Session) -> int | None:
    """Return the id of the default university's default section, if any."""
    university = crud.get_university_by_code(db, DEFAULT_UNIVERSITY["code"])
    if university is None:
        return None
    section = (
        db.query(Section)
        .join(crud.models.Course, Section.course_id == crud.models.Course.id)
        .join(Department, crud.models.Course.department_id == Department.id)
        .join(Faculty, Department.faculty_id == Faculty.id)
        .filter(Faculty.university_id == university.id)
        .order_by(Section.id)
        .first()
    )
    return section.id if section else None


def backfill_tenant_membership(db: Session) -> None:
    """Assign the default university to every tenant-less account and learner.

    Runs after the default org exists: users with ``university_id IS NULL``
    and students with ``university_id IS NULL`` are pointed at the default
    university. Idempotent.
    """
    university = crud.get_university_by_code(db, DEFAULT_UNIVERSITY["code"])
    if university is None:
        return

    db.query(User).filter(User.university_id.is_(None)).update(
        {"university_id": university.id}, synchronize_session=False
    )
    db.query(Student).filter(Student.university_id.is_(None)).update(
        {"university_id": university.id}, synchronize_session=False
    )
    db.query(crud.models.AuditLog).filter(crud.models.AuditLog.university_id.is_(None)).update(
        {"university_id": university.id}, synchronize_session=False
    )
    db.commit()


def enroll_all_students_in_default_section(db: Session) -> None:
    """Enroll every student who isn't enrolled anywhere into the default
    section — preserving the legacy MEC271 cohort's access to student-data
    and instructor endpoints. Idempotent."""
    section_id = get_default_section_id(db)
    if section_id is None:
        return
    orphan_students = (
        db.query(Student)
        .outerjoin(crud.models.Enrollment, crud.models.Enrollment.student_id == Student.student_id)
        .filter(crud.models.Enrollment.id.is_(None))
        .all()
    )
    for student in orphan_students:
        crud.enroll_student_in_section(db, student_id=student.student_id, section_id=section_id)
    db.commit()


def boot_default_organization() -> University:
    """Run the full default-org bootstrap inside a fresh session.

    Called once after table creation at app startup.
    """
    from .database import SessionLocal

    with SessionLocal() as db:
        university = ensure_default_organization(db)
        backfill_tenant_membership(db)
        enroll_all_students_in_default_section(db)
        return university
