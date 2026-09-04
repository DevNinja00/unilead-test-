"""Student state — DB-backed, per-student.

All functions take ``student_id`` as a parameter now. The Compass routes
pass the current user's ``student_id`` (resolved from the JWT via
``get_current_student``).
"""

from __future__ import annotations

import copy
from typing import Optional

from sqlalchemy.orm import Session

from ..db import SessionLocal, crud
from ..db.models import Student
from .mock_data import INITIAL_COMPETENCIES, INITIAL_OVERALL_PROGRESS

DEFAULT_STUDENT_ID = "api-gateway-student"


# --- Internal helpers ------------------------------------------------------

def _timeline_for_read(student_id: str) -> list[dict]:
    """Return the student's evidence timeline (newest-first), DB-backed."""
    db = SessionLocal()
    try:
        events = crud.list_evidence_events(db, student_id, newest_first=True)
        return [
            {
                "timestamp": e.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") if e.timestamp else "",
                "event_type": e.event_type,
                "competency_id": e.competency_id,
                "title": e.title,
                "detail": e.detail,
                "result": e.result,
            }
            for e in events
        ]
    finally:
        db.close()


def _load_state_from_db(student_id: str) -> dict:
    """Load the per-student state from the DB."""
    db = SessionLocal()
    try:
        student = crud.get_student_by_id(db, student_id)
        if student is None:
            # Fall back to in-memory defaults if the student doesn't exist yet
            return {
                "overall_progress": INITIAL_OVERALL_PROGRESS,
                "competencies": copy.deepcopy(INITIAL_COMPETENCIES),
            }
        comps = crud.get_competencies(db, student_id)
        return {
            "overall_progress": student.overall_progress,
            "competencies": [
                {
                    "id": c.competency_id,
                    "name": c.competency_name,
                    "status": c.status,
                    "progress": c.progress,
                }
                for c in comps
            ],
        }
    finally:
        db.close()


def get_overall_progress(student_id: str = DEFAULT_STUDENT_ID) -> int:
    return _load_state_from_db(student_id)["overall_progress"]


def get_competencies(student_id: str = DEFAULT_STUDENT_ID) -> list[dict]:
    return _load_state_from_db(student_id)["competencies"]


def get_competency(competency_id: str, student_id: str = DEFAULT_STUDENT_ID) -> dict | None:
    for c in get_competencies(student_id):
        if c["id"] == competency_id:
            return c
    return None


def get_active_competency(student_id: str = DEFAULT_STUDENT_ID) -> dict:
    """The competency currently being worked on — the first one that's
    not 'demonstrated', falling back to the first competency overall."""
    comps = get_competencies(student_id)
    for c in comps:
        if c["status"] != "demonstrated":
            return c
    return comps[0]


def bump_competency_progress(
    competency_id: str,
    amount: int,
    student_id: str = DEFAULT_STUDENT_ID,
    cap: int = 92,
) -> dict | None:
    """Increase a competency's progress in the DB (capped)."""
    db = SessionLocal()
    try:
        c = next(
            (x for x in crud.get_competencies(db, student_id) if x.competency_id == competency_id),
            None,
        )
        if c is None:
            return None
        new_progress = min(cap, c.progress + amount)
        crud.upsert_competency(
            db,
            student_id=student_id,
            competency_id=c.competency_id,
            competency_name=c.competency_name,
            status=c.status,
            progress=new_progress,
        )
        db.commit()
        return {"id": c.competency_id, "name": c.competency_name, "status": c.status, "progress": new_progress}
    finally:
        db.close()


def bump_overall_progress(amount: int, student_id: str = DEFAULT_STUDENT_ID) -> int:
    db = SessionLocal()
    try:
        student = crud.get_student_by_id(db, student_id)
        if student is None:
            return INITIAL_OVERALL_PROGRESS
        new_val = min(100, student.overall_progress + amount)
        crud.update_student_progress(db, student_id, new_val)
        db.commit()
        return new_val
    finally:
        db.close()


def reset_state(student_id: str = DEFAULT_STUDENT_ID) -> None:
    """Mostly a test helper — not exposed via any route."""
    db = SessionLocal()
    try:
        student = crud.get_student_by_id(db, student_id)
        if student is None:
            return
        for c in INITIAL_COMPETENCIES:
            crud.upsert_competency(
                db,
                student_id=student_id,
                competency_id=c["id"],
                competency_name=c["name"],
                status=c["status"],
                progress=c["progress"],
            )
        crud.update_student_progress(db, student_id, INITIAL_OVERALL_PROGRESS)
        db.commit()
    finally:
        db.close()


# --- Multi-student registry API (preserved, now DB-backed) ------------------


def list_students() -> list[dict]:
    db = SessionLocal()
    try:
        students = crud.list_all_students(db)
        result = []
        for s in students:
            comps = crud.get_competencies(db, s.student_id)
            result.append(
                {
                    "student_id": s.student_id,
                    "display_name": s.display_name,
                    "course_code": s.course_code,
                    "course_title": s.course_title,
                    "overall_progress": s.overall_progress,
                    "competencies": [
                        {
                            "id": c.competency_id,
                            "name": c.competency_name,
                            "status": c.status,
                            "progress": c.progress,
                        }
                        for c in comps
                    ],
                }
            )
        return result
    finally:
        db.close()


def get_student_by_id(student_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        s = crud.get_student_by_id(db, student_id)
        if s is None:
            return None
        comps = crud.get_competencies(db, student_id)
        return {
            "student_id": s.student_id,
            "display_name": s.display_name,
            "course_code": s.course_code,
            "course_title": s.course_title,
            "overall_progress": s.overall_progress,
            "competencies": [
                {
                    "id": c.competency_id,
                    "name": c.competency_name,
                    "status": c.status,
                    "progress": c.progress,
                }
                for c in comps
            ],
            "evidence_timeline": _timeline_for_read(student_id),
        }
    finally:
        db.close()


def get_aggregate_by_competency() -> list[dict]:
    db = SessionLocal()
    try:
        all_students = crud.list_all_students(db)
        if not all_students:
            return []
        # Build a stable competency list from INITIAL_COMPETENCIES — every
        # student has the same 5 MEC271 competencies (seeded on signup).
        rows = []
        for c in INITIAL_COMPETENCIES:
            row = {
                "competency_id": c["id"],
                "competency_name": c["name"],
                "demonstrated": 0,
                "developing": 0,
                "needs_practice": 0,
                "not_started": 0,
            }
            for s in all_students:
                sc = next(
                    (x for x in crud.get_competencies(db, s.student_id) if x.competency_id == c["id"]),
                    None,
                )
                if sc is None:
                    continue
                if sc.status in row:
                    row[sc.status] += 1
            rows.append(row)
        return rows
    finally:
        db.close()


def append_evidence_event(
    student_id: str,
    event_type: str,
    title: str,
    detail: str,
    result: str = "INFO",
    competency_id: Optional[str] = None,
) -> None:
    """Append an event to a student's evidence timeline (now DB-backed)."""
    db = SessionLocal()
    try:
        crud.append_evidence_event(
            db,
            student_id=student_id,
            event_type=event_type,
            title=title,
            detail=detail,
            result=result,
            competency_id=competency_id,
        )
        db.commit()
    finally:
        db.close()


def get_default_student_id() -> str:
    return DEFAULT_STUDENT_ID


def sync_default_student_snapshot() -> None:
    """No-op now — DB is the source of truth, nothing to sync."""
    pass
