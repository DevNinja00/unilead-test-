from fastapi import APIRouter, Depends, Request

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.diagnostic import (
    DiagnosticQuestion,
    DiagnosticResult,
    DiagnosticSubmission,
)
from ..services import diagnostic_service

router = APIRouter(prefix="/api/diagnostic", tags=["diagnostic"])


@router.get("/questions", response_model=list[DiagnosticQuestion])
def get_questions(current_student: Student = Depends(get_current_student)) -> list[dict]:
    return diagnostic_service.get_questions()


@router.post("", response_model=list[DiagnosticResult])
def submit_diagnostic(
    submission: DiagnosticSubmission,
    http_request: Request,
    current_student: Student = Depends(get_current_student),
) -> list[dict]:
    answers = [a.model_dump() for a in submission.answers]
    return diagnostic_service.submit_diagnostic(answers, http_request, current_student.student_id)
