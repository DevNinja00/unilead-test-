"""Instructor router — read-only views over the student registry.

Three endpoints:
  - ``GET /api/instructor/summary``         → class-level totals
  - ``GET /api/instructor/aggregate``        → per-competency status counts
  - ``GET /api/instructor/students``         → roster of all students
  - ``GET /api/instructor/students/{id}``    → one student's full record + timeline
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from ..auth.dependencies import get_current_instructor
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


@router.get("/summary", response_model=InstructorClassSummary)
def get_class_summary(current_user: User = Depends(get_current_instructor)) -> dict:
    """Return high-level class numbers (total students, average progress, etc.)."""
    _log.debug("class summary requested by instructor=%d", current_user.id)
    return instructor_service.get_class_summary()


@router.get("/aggregate", response_model=list[InstructorCompetencyAggregate])
def get_competency_aggregate(current_user: User = Depends(get_current_instructor)) -> list[dict]:
    """For each competency, count how many students are at each status."""
    _log.debug("competency aggregate requested by instructor=%d", current_user.id)
    return instructor_service.get_competency_aggregate()


@router.get("/students", response_model=list[InstructorStudentSummary])
def list_students(current_user: User = Depends(get_current_instructor)) -> list[dict]:
    """Return the roster of all students (without timeline payload)."""
    _log.debug("student roster requested by instructor=%d", current_user.id)
    return instructor_service.list_all_students()


@router.get("/students/{student_id}", response_model=InstructorStudentDetail)
def get_student_detail(
    student_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    current_user: User = Depends(get_current_instructor),
) -> dict:
    """Return one student's full record including their evidence timeline."""
    _log.info("student detail requested by instructor=%d student=%s", current_user.id, student_id)
    detail = instructor_service.get_student_detail(student_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail="No student found with the given ID.",
        )
    return detail
