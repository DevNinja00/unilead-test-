from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.learning import PracticeTask
from ..services import learning_service

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.get("/{competency_id}", response_model=PracticeTask)
def get_practice_task(competency_id: str, current_student: Student = Depends(get_current_student)) -> dict:
    return learning_service.get_practice_task(competency_id)
