import logging

from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.onboarding import OnboardingAnswers, OnboardingResponse
from ..services import onboarding_service

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
_log = logging.getLogger("unilead.onboarding")


@router.post("", response_model=OnboardingResponse)
def submit_onboarding(
    answers: OnboardingAnswers,
    current_student: Student = Depends(get_current_student),
) -> OnboardingResponse:
    _log.info("onboarding submitted by student=%s", current_student.student_id)
    result = onboarding_service.submit_onboarding(answers.model_dump(), current_student.student_id)
    return OnboardingResponse(**result)
