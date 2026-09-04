"""Transfer router — presents a transfer task and evaluates the response."""

import logging

from fastapi import APIRouter, Depends, Path, Request

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.transfer import (
    TransferEvaluationRequest,
    TransferEvaluationResponse,
    TransferScenarioResponse,
)
from ..services import transfer_service

router = APIRouter(prefix="/api/transfer", tags=["transfer"])
_log = logging.getLogger("unilead.transfer")


@router.get("/{competency_id}", response_model=TransferScenarioResponse)
def get_transfer_scenario(
    competency_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    http_request: Request = ...,
    current_student: Student = Depends(get_current_student),
    scenario_id: str | None = None,
) -> dict:
    """Present a transfer task (Plant B) for the given competency, scoped
    to the current student's evidence history.
    """
    _log.info(
        "transfer scenario requested student=%s competency=%s",
        current_student.student_id,
        competency_id,
    )
    return transfer_service.get_scenario(
        competency_id, scenario_id, http_request, current_student.student_id
    )


@router.post("/{competency_id}", response_model=TransferEvaluationResponse)
def evaluate_transfer(
    competency_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    request: TransferEvaluationRequest = ...,
    http_request: Request = ...,
    current_student: Student = Depends(get_current_student),
) -> dict:
    """Evaluate the student's free-text response to a transfer prompt."""
    _log.info(
        "transfer evaluation student=%s competency=%s", current_student.student_id, competency_id
    )
    return transfer_service.evaluate_response(
        competency_id, request, http_request, current_student.student_id
    )
