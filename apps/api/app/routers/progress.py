import logging

from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.progress import ProgressResponse
from ..services import progress_service

router = APIRouter(prefix="/api/progress", tags=["progress"])
_log = logging.getLogger("unilead.progress")


@router.get("", response_model=ProgressResponse)
def get_progress(current_student: Student = Depends(get_current_student)) -> dict:
    _log.debug("progress requested by student=%s", current_student.student_id)
    return progress_service.get_progress_summary(current_student.student_id)
