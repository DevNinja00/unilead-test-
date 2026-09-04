"""AI Coach router — accepts a coach turn and returns the orchestrator's reply."""

from fastapi import APIRouter, Depends, Request

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.coach import CoachRequest, CoachResponse
from ..services import coach_service

router = APIRouter(prefix="/api/coach", tags=["coach"])


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
    return await coach_service.process_turn(request, http_request, current_student.student_id)
