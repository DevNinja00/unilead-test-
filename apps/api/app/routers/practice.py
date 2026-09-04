import logging

from fastapi import APIRouter, Depends, Path

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.learning import PracticeTask
from ..services import learning_service

router = APIRouter(prefix="/api/practice", tags=["practice"])
_log = logging.getLogger("unilead.practice")


@router.get("/{competency_id}", response_model=PracticeTask)
def get_practice_task(
    competency_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    current_student: Student = Depends(get_current_student),
) -> dict:
    _log.debug("practice task requested student=%s competency=%s", current_student.student_id, competency_id)
    return learning_service.get_practice_task(competency_id)
