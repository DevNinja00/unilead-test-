import logging

from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.common import Competency
from ..services import progress_service

router = APIRouter(prefix="/api/competencies", tags=["competencies"])
_log = logging.getLogger("unilead.competencies")


@router.get("", response_model=list[Competency])
def get_competencies(current_student: Student = Depends(get_current_student)) -> list[dict]:
    """Return the current student's competency list (from the DB)."""
    _log.debug("competencies requested by student=%s", current_student.student_id)
    return progress_service.get_full_competencies(current_student.student_id)
