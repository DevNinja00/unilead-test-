"""Admin router — university identity & multi-tenant provisioning (Sprint 3).

Two privilege tiers:

* SUPER_ADMIN: create/list/toggle universities, provision university admins,
  and read the global audit trail.
* UNIVERSITY_ADMIN: manage their own university's org tree
  (faculties → departments → courses → sections), enroll/unenroll students,
  provision instructors and students, and read their university's audit rows.

Instructors never touch this router — they see section-scoped data via the
instructor router.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth.dependencies import (
    get_current_admin,
    get_current_super_admin,
    get_current_university_admin,
)
from ..auth.service import hash_password
from ..db import crud, get_db
from ..db.models import User
from ..schemas.admin import (
    AdminStudentOut,
    CourseCreate,
    CourseOut,
    DepartmentCreate,
    DepartmentOut,
    EnrollmentOut,
    EnrollmentRequest,
    FacultyCreate,
    FacultyOut,
    InstructorCreate,
    MessageOut,
    OrgTreeOut,
    SectionCreate,
    SectionOut,
    StudentCreate,
    UniversityAdminCreate,
    UniversityCreate,
    UniversityOut,
)
from ..services.mock_data import INITIAL_COMPETENCIES

router = APIRouter(prefix="/api/admin", tags=["admin"])

_log = logging.getLogger("unilead.admin")


# --- Helpers ----------------------------------------------------------------


def _audit(
    db: Session,
    *,
    action: str,
    user: User,
    request: Request,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str = "",
    outcome: str = "OK",
    university_id: int | None = None,
) -> None:
    ip = request.client.host if request.client else "unknown"
    crud.add_audit_log(
        db,
        actor_user_id=user.id,
        actor_role=(user.role or "student"),
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip,
        outcome=outcome,
        university_id=university_id,
    )


def _student_id_for_user(user_id: int) -> str:
    return f"u{user_id}-student"


def _seed_initial_competencies(db: Session, student_id: str) -> None:
    for c in INITIAL_COMPETENCIES:
        crud.upsert_competency(
            db,
            student_id=student_id,
            competency_id=c["id"],
            competency_name=c["name"],
            status=c["status"],
            progress=c["progress"],
        )


def _university_or_404(db: Session, university_id: int):
    university = crud.get_university_by_id(db, university_id)
    if university is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found.")
    return university


def _university_out(university) -> dict:
    """Map a University ORM row (JSON-string ``email_domains``) to a UnivOut."""
    import json

    try:
        domains = json.loads(university.email_domains or "[]")
    except json.JSONDecodeError:
        domains = []
    return {
        "id": university.id,
        "code": university.code,
        "name": university.name,
        "email_domains": domains if isinstance(domains, list) else [],
        "is_active": university.is_active,
    }


def _faculty_or_404(db: Session, faculty_id: int):
    faculty = db.query(crud.models.Faculty).filter(crud.models.Faculty.id == faculty_id).first()
    if faculty is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found.")
    return faculty


def _department_or_404(db: Session, department_id: int):
    department = (
        db.query(crud.models.Department).filter(crud.models.Department.id == department_id).first()
    )
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")
    return department


def _course_or_404(db: Session, course_id: int):
    course = db.query(crud.models.Course).filter(crud.models.Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    return course


def _section_or_404(db: Session, section_id: int):
    section = db.query(crud.models.Section).filter(crud.models.Section.id == section_id).first()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    return section


def _assert_university_scope(db: Session, admin: User, university_id: int) -> None:
    """UNIVERSITY_ADMIN may only touch their own university."""
    if admin.role == "super_admin":
        return
    if admin.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to that university.",
        )


def _org_tree(db: Session, university_id: int) -> dict:
    university = _university_or_404(db, university_id)
    faculties = []
    for faculty in crud.get_faculties_for_university(db, university_id):
        departments = []
        for dept in crud.get_departments_for_faculty(db, faculty.id):
            courses = []
            for course in crud.get_courses_for_department(db, dept.id):
                sections = [
                    {
                        "id": s.id,
                        "term": s.term,
                        "code": s.code,
                        "instructor_user_id": s.instructor_user_id,
                        "enrolled_students": len(s.enrollments),
                    }
                    for s in crud.get_sections_for_course(db, course.id)
                ]
                courses.append(
                    {
                        "id": course.id,
                        "code": course.code,
                        "title": course.title,
                        "credits": course.credits,
                        "sections": sections,
                    }
                )
            departments.append(
                {
                    "id": dept.id,
                    "code": dept.code,
                    "name": dept.name,
                    "courses": courses,
                }
            )
        faculties.append(
            {
                "id": faculty.id,
                "code": faculty.code,
                "name": faculty.name,
                "departments": departments,
            }
        )
    return {
        "university_id": university.id,
        "university_code": university.code,
        "university_name": university.name,
        "faculties": faculties,
    }


# --- SUPER_ADMIN: university lifecycle --------------------------------------


@router.get("/universities", response_model=list[UniversityOut])
def list_universities(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    return [_university_out(u) for u in crud.list_universities(db)]


@router.post("/universities", response_model=UniversityOut, status_code=status.HTTP_201_CREATED)
def create_university(
    req: UniversityCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    if crud.get_university_by_code(db, req.code) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"University code '{req.code.strip().upper()}' already exists.",
        )
    university = crud.create_university(
        db, code=req.code, name=req.name, email_domains=req.email_domains
    )
    _audit(
        db,
        action="university.create",
        user=admin,
        request=request,
        target_type="university",
        target_id=str(university.id),
        detail=f"{university.code} — {university.name}",
        university_id=university.id,
    )
    db.commit()
    return _university_out(university)


@router.get("/universities/{code}", response_model=OrgTreeOut)
def get_university_tree(
    code: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    university = crud.get_university_by_code(db, code)
    if university is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found.")
    return _org_tree(db, university.id)


@router.delete("/universities/{code}", response_model=MessageOut)
def deactivate_university(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    university = crud.get_university_by_code(db, code)
    if university is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found.")
    university.is_active = False
    _audit(
        db,
        action="university.deactivate",
        user=admin,
        request=request,
        target_type="university",
        target_id=str(university.id),
        university_id=university.id,
    )
    db.commit()
    return {"message": f"University '{code}' deactivated."}


@router.post(
    "/users/university-admins",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def provision_university_admin(
    req: UniversityAdminCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    """Create a UNIVERSITY_ADMIN account bound to an existing university."""
    if (
        crud.get_user_by_email(db, req.email) is not None
        or crud.get_user_by_username(db, req.username.lower()) is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or username already exists.",
        )

    university = crud.get_university_by_code(db, req.university_code)
    if university is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found.")

    try:
        user = crud.create_user(
            db,
            email=req.email,
            username=req.username.lower(),
            name=req.name,
            password_hash=hash_password(req.password),
            role="university_admin",
            university_id=university.id,
            email_verified=True,
        )
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or username already exists.",
        ) from None

    _audit(
        db,
        action="university_admin.create",
        user=admin,
        request=request,
        target_type="user",
        target_id=str(user.id),
        detail=f"Created university admin '{req.username}' for {university.code}.",
        university_id=university.id,
    )
    db.commit()
    return {"message": f"University admin '{req.username}' created for '{university.code}'."}


# --- UNIVERSITY_ADMIN: org tree ---------------------------------------------


@router.get("/org", response_model=OrgTreeOut)
def my_org_tree(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    return _org_tree(db, admin.university_id)


@router.post("/org/faculties", response_model=FacultyOut, status_code=status.HTTP_201_CREATED)
def create_faculty(
    req: FacultyCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    _university_or_404(db, admin.university_id)
    faculty = crud.create_faculty(
        db, university_id=admin.university_id, code=req.code, name=req.name
    )
    _audit(
        db,
        action="faculty.create",
        user=admin,
        request=request,
        target_type="faculty",
        target_id=str(faculty.id),
        detail=f"{faculty.code} — {faculty.name}",
        university_id=admin.university_id,
    )
    db.commit()
    return faculty


@router.post("/org/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    req: DepartmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    faculty = _faculty_or_404(db, req.faculty_id)
    _assert_university_scope(db, admin, faculty.university_id)
    department = crud.create_department(db, faculty_id=faculty.id, code=req.code, name=req.name)
    _audit(
        db,
        action="department.create",
        user=admin,
        request=request,
        target_type="department",
        target_id=str(department.id),
        detail=f"{department.code} — {department.name}",
        university_id=admin.university_id,
    )
    db.commit()
    return department


@router.post("/org/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    req: CourseCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    department = _department_or_404(db, req.department_id)
    _assert_university_scope(db, admin, department.faculty.university_id)
    course = crud.create_course(
        db, department_id=department.id, code=req.code, title=req.title, credits=req.credits
    )
    _audit(
        db,
        action="course.create",
        user=admin,
        request=request,
        target_type="course",
        target_id=str(course.id),
        detail=f"{course.code} — {course.title}",
        university_id=admin.university_id,
    )
    db.commit()
    return course


@router.post("/org/sections", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
def create_section(
    req: SectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    course = _course_or_404(db, req.course_id)
    _assert_university_scope(db, admin, course.department.faculty.university_id)
    section = crud.create_section(
        db,
        course_id=course.id,
        term=req.term,
        code=req.code,
        instructor_user_id=req.instructor_user_id,
    )
    _audit(
        db,
        action="section.create",
        user=admin,
        request=request,
        target_type="section",
        target_id=str(section.id),
        detail=f"{course.code} — section {section.code} ({section.term})",
        university_id=admin.university_id,
    )
    db.commit()
    return section


@router.get("/org/sections/{section_id}/students", response_model=list[AdminStudentOut])
def section_roster(
    section_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    section = _section_or_404(db, section_id)
    _assert_university_scope(db, admin, section.course.department.faculty.university_id)
    return crud.get_students_in_section(db, section_id)


# --- UNIVERSITY_ADMIN: enrollment -------------------------------------------


@router.post("/org/enroll", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED)
def enroll_student(
    req: EnrollmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    student = crud.get_student_by_id(db, req.student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    section = _section_or_404(db, req.section_id)
    section_university_id = section.course.department.faculty.university_id
    _assert_university_scope(db, admin, student.university_id or admin.university_id)
    _assert_university_scope(db, admin, section_university_id)

    enrollment = crud.enroll_student_in_section(
        db, student_id=student.student_id, section_id=section.id
    )
    _audit(
        db,
        action="enrollment.create",
        user=admin,
        request=request,
        target_type="enrollment",
        target_id=f"{student.student_id}:{section.id}",
        detail=f"{student.student_id} → section {section.id}",
        university_id=section_university_id,
    )
    db.commit()
    return enrollment


@router.delete("/org/sections/{section_id}/students/{student_id}", response_model=MessageOut)
def unenroll_student(
    section_id: int,
    student_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    student = crud.get_student_by_id(db, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    section = _section_or_404(db, section_id)
    section_university_id = section.course.department.faculty.university_id
    _assert_university_scope(db, admin, section_university_id)

    removed = crud.unenroll_student_from_section(
        db, student_id=student.student_id, section_id=section.id
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found.")
    _audit(
        db,
        action="enrollment.delete",
        user=admin,
        request=request,
        target_type="enrollment",
        target_id=f"{student.student_id}:{section.id}",
        detail=f"{student.student_id} removed from section {section.id}",
        university_id=section_university_id,
    )
    db.commit()
    return {"message": "Student unenrolled."}


# --- UNIVERSITY_ADMIN: provisioning -----------------------------------------


@router.post("/org/instructors", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def provision_instructor(
    req: InstructorCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    if (
        crud.get_user_by_email(db, req.email) is not None
        or crud.get_user_by_username(db, req.username.lower()) is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or username already exists.",
        )
    try:
        user = crud.create_user(
            db,
            email=req.email,
            username=req.username.lower(),
            name=req.name,
            password_hash=hash_password(req.password),
            role="instructor",
            university_id=admin.university_id,
            email_verified=True,
        )
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or username already exists.",
        ) from None
    _audit(
        db,
        action="instructor.create",
        user=admin,
        request=request,
        target_type="user",
        target_id=str(user.id),
        detail=f"Provisioned instructor '{req.username}'.",
        university_id=admin.university_id,
    )
    db.commit()
    return {"message": f"Instructor '{req.username}' created."}


@router.post("/org/students", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def provision_student(
    req: StudentCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_university_admin),
):
    if (
        crud.get_user_by_email(db, req.email) is not None
        or crud.get_user_by_username(db, req.username.lower()) is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or username already exists.",
        )
    try:
        user = crud.create_user(
            db,
            email=req.email,
            username=req.username.lower(),
            name=req.name,
            password_hash=hash_password(req.password),
            role="student",
            university_id=admin.university_id,
            email_verified=True,
        )
        db.flush()
        student = crud.create_student(
            db,
            student_id=_student_id_for_user(user.id),
            user_id=user.id,
            display_name=req.name,
            course_code=req.course_code,
            course_title=req.course_title,
            university_id=admin.university_id,
        )
        _seed_initial_competencies(db, student.student_id)
        if req.section_id is not None:
            section = _section_or_404(db, req.section_id)
            _assert_university_scope(db, admin, section.course.department.faculty.university_id)
            crud.enroll_student_in_section(db, student_id=student.student_id, section_id=section.id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or username already exists.",
        ) from None
    _audit(
        db,
        action="student.create",
        user=admin,
        request=request,
        target_type="user",
        target_id=str(user.id),
        detail=f"Provisioned student '{req.username}' (id {student.student_id}).",
        university_id=admin.university_id,
    )
    db.commit()
    return {"message": f"Student created with id '{student.student_id}'."}


# --- Audit trails -----------------------------------------------------------


@router.get("/audit")
def list_audit(
    request: Request,
    university_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Latest audit entries. UNIVERSITY_ADMIN is auto-scoped to their own
    university; SUPER_ADMIN may filter across tenants by ``university_id``."""
    query = db.query(crud.models.AuditLog)
    if admin.role == "super_admin":
        if university_id is not None:
            _university_or_404(db, university_id)
            query = query.filter(crud.models.AuditLog.university_id == university_id)
    else:
        query = query.filter(crud.models.AuditLog.university_id == admin.university_id)
    entries = query.order_by(crud.models.AuditLog.id.desc()).limit(min(max(limit, 1), 200)).all()
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "actor_user_id": e.actor_user_id,
            "actor_role": e.actor_role,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "detail": e.detail,
            "outcome": e.outcome,
            "university_id": e.university_id,
        }
        for e in entries
    ]
