"""Instructor router — read-only views over the student registry.

Three endpoints:
  - ``GET /api/instructor/summary``         → class-level totals
  - ``GET /api/instructor/aggregate``        → per-competency status counts
  - ``GET /api/instructor/students``         → roster of all students
  - ``GET /api/instructor/students/{id}``    → one student's full record + timeline
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_instructor
from ..db import crud, get_db
from ..db.models import User
from ..schemas.instructor import (
    InstructorClassSummary,
    InstructorCompetencyAggregate,
    InstructorStudentDetail,
    InstructorStudentSummary,
)
from ..services import instructor_service

router = APIRouter(prefix="/api/instructor", tags=["instructor"])
_log = logging.getLogger("unilead.instructor")


def _audit_instructor_view(
    db: Session, *, current_user: User, ip: str, view: str, target_id: str | None = None
) -> None:
    """Record an instructor read for the audit trail."""
    crud.add_audit_log(
        db,
        actor_user_id=current_user.id,
        actor_role=current_user.role or "instructor",
        action="instructor_view",
        target_type="student" if target_id else "class",
        target_id=target_id,
        detail=f"instructor read view={view}",
        ip_address=ip,
        outcome="OK",
    )


@router.get("/summary", response_model=InstructorClassSummary)
def get_class_summary(
    request: Request,
    current_user: User = Depends(get_current_instructor),
    db: Session = Depends(get_db),
) -> dict:
    """Return high-level class numbers (total students, average progress, etc.)."""
    ip = request.client.host if request.client else "unknown"
    _audit_instructor_view(db, current_user=current_user, ip=ip, view="summary")
    db.commit()
    _log.debug("class summary requested by instructor=%d", current_user.id)
    return instructor_service.get_class_summary()


@router.get("/aggregate", response_model=list[InstructorCompetencyAggregate])
def get_competency_aggregate(
    request: Request,
    current_user: User = Depends(get_current_instructor),
    db: Session = Depends(get_db),
) -> list[dict]:
    """For each competency, count how many students are at each status."""
    ip = request.client.host if request.client else "unknown"
    _audit_instructor_view(db, current_user=current_user, ip=ip, view="aggregate")
    db.commit()
    _log.debug("competency aggregate requested by instructor=%d", current_user.id)
    return instructor_service.get_competency_aggregate()


@router.get("/students", response_model=list[InstructorStudentSummary])
def list_students(
    request: Request,
    current_user: User = Depends(get_current_instructor),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return the roster of all students (without timeline payload)."""
    ip = request.client.host if request.client else "unknown"
    _audit_instructor_view(db, current_user=current_user, ip=ip, view="students")
    db.commit()
    _log.debug("student roster requested by instructor=%d", current_user.id)
    return instructor_service.list_all_students()


@router.get("/students/{student_id}", response_model=InstructorStudentDetail)
def get_student_detail(
    student_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    request: Request = None,  # type: ignore[assignment]
    current_user: User = Depends(get_current_instructor),
    db: Session = Depends(get_db),
) -> dict:
    """Return one student's full record including their evidence timeline."""
    ip = request.client.host if request.client else "unknown"
    _audit_instructor_view(
        db, current_user=current_user, ip=ip, view="student_detail", target_id=student_id
    )
    db.commit()
    _log.info("student detail requested by instructor=%d student=%s", current_user.id, student_id)
    detail = instructor_service.get_student_detail(student_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail="No student found with the given ID.",
        )
    return detail
