"""Remediation router — returns a targeted micro-lesson for a failing competency."""

import logging

from fastapi import APIRouter, Depends, Path, Request

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.remediation import RemediationPlanResponse
from ..services import remediation_service

router = APIRouter(prefix="/api/remediation", tags=["remediation"])
_log = logging.getLogger("unilead.remediation")


@router.get("/{competency_id}", response_model=RemediationPlanResponse)
def get_remediation_plan(
    competency_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    http_request: Request = ...,
    current_student: Student = Depends(get_current_student),
) -> dict:
    """Build a remediation plan for the given competency using the current
    student's evidence history.
    """
    _log.info(
        "remediation plan requested student=%s competency=%s",
        current_student.student_id,
        competency_id,
    )
    return remediation_service.build_plan(competency_id, http_request, current_student.student_id)
