"""Evidence service — exposes a student's chronological event log.

The timeline is built from events appended by the wired services
(coach_service, simulation_service, diagnostic_service,
transfer_service). Each event has a timestamp, an event_type, a title,
a human-readable detail, and a result (PASS / FAIL / INFO).

This service is read-only: it just reads from the multi-student registry
in ``student_state``. No AI, no LLM.
"""

from __future__ import annotations

from fastapi import HTTPException

from . import student_state


def get_timeline(student_id: str) -> list[dict]:
    """Return a student's evidence timeline, newest-first."""
    student = student_state.get_student_by_id(student_id)
    if student is None:
        raise HTTPException(
            status_code=404,
            detail=f"No student found with id {student_id!r}",
        )
    timeline = student.get("evidence_timeline", [])
    # Newest first — feels more natural for a "what just happened?" feed.
    return list(reversed(timeline))
