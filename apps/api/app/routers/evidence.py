"""Evidence router — read-only views of a student's evidence timeline.

The ``student_id`` is taken from the JWT (``get_current_student``) for the
student-facing route, and from the URL for the instructor-facing route.
"""

import logging

from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_instructor, get_current_student
from ..db.models import Student, User
from ..schemas.instructor import EvidenceEvent
from ..services import evidence_service

router = APIRouter(prefix="/api/evidence", tags=["evidence"])
_log = logging.getLogger("unilead.evidence")


@router.get("/me/timeline", response_model=list[EvidenceEvent])
def get_my_timeline(current_student: Student = Depends(get_current_student)) -> list[dict]:
    """Return the current student's evidence timeline, newest-first."""
    _log.debug("evidence timeline requested by student=%s", current_student.student_id)
    return evidence_service.get_timeline(current_student.student_id)


@router.get("/{student_id}/timeline", response_model=list[EvidenceEvent])
def get_student_timeline(
    student_id: str,
    current_user: User = Depends(get_current_instructor),
) -> list[dict]:
    """Instructor view: return any student's evidence timeline by student_id."""
    _log.info("evidence timeline requested by instructor=%d for student=%s", current_user.id, student_id)
    return evidence_service.get_timeline(student_id)
