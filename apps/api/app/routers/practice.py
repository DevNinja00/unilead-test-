from fastapi import APIRouter

from ..schemas.learning import PracticeTask
from ..services import learning_service

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.get("/{competency_id}", response_model=PracticeTask)
def get_practice_task(competency_id: str) -> dict:
    return learning_service.get_practice_task(competency_id)
