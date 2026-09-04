"""Onboarding service — persists the four onboarding answers to the DB
for a specific student.
"""

import logging

from .mock_data import COURSE_CODE, COURSE_TITLE

_log = logging.getLogger("unilead.onboarding")


def submit_onboarding(answers: dict, student_id: str) -> dict:
    """Persist onboarding answers to the DB and acknowledge receipt."""
    try:
        from ..db import SessionLocal, crud

        db = SessionLocal()
        try:
            crud.save_onboarding(
                db,
                student_id=student_id,
                learning_challenge=answers.get("learning_challenge", ""),
                preferred_method=answers.get("preferred_method", ""),
                obstacle=answers.get("obstacle", ""),
                goal=answers.get("goal", ""),
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to persist onboarding for student=%s", student_id, exc_info=True)
    return {"success": True, "course_code": COURSE_CODE, "course_title": COURSE_TITLE}
