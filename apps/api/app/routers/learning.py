import logging

from fastapi import APIRouter, Depends, Path

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.learning import LessonSection
from ..services import learning_service

router = APIRouter(prefix="/api/learning", tags=["learning"])
_log = logging.getLogger("unilead.learning")


@router.get("/{competency_id}", response_model=list[LessonSection])
def get_lesson(
    competency_id: str = Path(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    current_student: Student = Depends(get_current_student),
) -> list[dict]:
    _log.debug(
        "lesson requested student=%s competency=%s", current_student.student_id, competency_id
    )
    return learning_service.get_lesson(competency_id)
