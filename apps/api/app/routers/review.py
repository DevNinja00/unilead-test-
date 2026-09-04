from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.review import ReviewRequest, ReviewResponse
from ..services import review_service

router = APIRouter(prefix="/api/review", tags=["review"])


@router.post("", response_model=ReviewResponse)
def submit_review(
    request: ReviewRequest,
    current_student: Student = Depends(get_current_student),
) -> dict:
    return review_service.get_review(
        request.competency_id, request.finalize, current_student.student_id
    )
