"""Progress service — returns the live competency + progress state for one
student.

Each call opens a short DB session and reads the current student's
competency snapshots. The Mastery engine runs *inside* the simulation /
transfer flows — when a competency is promoted to MASTERED, this service
just reads the resulting status from the DB.
"""

from __future__ import annotations

from . import student_state
from .mock_data import COURSE_CODE, COURSE_TITLE


def get_progress_summary(student_id: str) -> dict:
    competencies = student_state.get_competencies(student_id)
    active = student_state.get_active_competency(student_id)

    return {
        "overall_progress": student_state.get_overall_progress(student_id),
        "competencies": [{"name": c["name"], "status": c["status"]} for c in competencies],
        "recommended_next_activity": f"{active['name']} Practice",
        "course_code": COURSE_CODE,
        "course_title": COURSE_TITLE,
    }


def get_full_competencies(student_id: str) -> list[dict]:
    return student_state.get_competencies(student_id)
