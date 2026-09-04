"""AI Coach router — accepts a coach turn and returns the orchestrator's reply."""

import logging

from fastapi import APIRouter, Depends, Request

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.coach import CoachRequest, CoachResponse
from ..services import coach_service

router = APIRouter(prefix="/api/coach", tags=["coach"])
_log = logging.getLogger("unilead.coach")


@router.post("", response_model=CoachResponse)
async def send_message(
    request: CoachRequest,
    http_request: Request,
    current_student: Student = Depends(get_current_student),
) -> dict:
    """Process one coach turn for the current student.

    The orchestrator runs in a per-user manager pool (see
    ``services.manager_pool``) so each student has their own evidence
    history and competency state.
    """
    _log.info("coach turn for student=%s mode=%s", current_student.student_id, request.mode)
    return await coach_service.process_turn(request, http_request, current_student.student_id)
