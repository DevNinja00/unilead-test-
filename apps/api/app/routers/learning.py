from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.learning import LessonSection
from ..services import learning_service

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/{competency_id}", response_model=list[LessonSection])
def get_lesson(competency_id: str, current_student: Student = Depends(get_current_student)) -> list[dict]:
    return learning_service.get_lesson(competency_id)
