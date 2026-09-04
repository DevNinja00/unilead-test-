from fastapi import APIRouter

from ..schemas.learning import LessonSection
from ..services import learning_service

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/{competency_id}", response_model=list[LessonSection])
def get_lesson(competency_id: str) -> list[dict]:
    return learning_service.get_lesson(competency_id)
