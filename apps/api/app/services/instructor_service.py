"""Instructor service — section-scoped aggregate views over the DB.

The instructor UI needs:
  - A roster of students in the sections *this instructor teaches* — never
    the whole registry (multi-tenant isolation, Sprint 3).
  - An aggregate per-competency view over that roster.
  - A single student's full record including their evidence timeline, only
    when the student is enrolled in one of the instructor's sections.

All data comes from the DB (via ``crud``) — no LLM, no AI in this layer.
Every function takes the ``instructor_user_id`` so scope is enforced at the
query level, not by filtering results afterwards.
"""

from __future__ import annotations

import collections

from sqlalchemy.orm import Session

from ..db import crud
from .mock_data import INITIAL_COMPETENCIES


def _scoped_students(db: Session, instructor_user_id: int) -> list:
    """Students enrolled in any section the instructor teaches."""
    return crud.get_students_for_instructor(db, instructor_user_id)


def _student_payloads(db: Session, students: list) -> list[dict]:
    """Build the roster payload (no timeline) for the given students."""
    if not students:
        return []
    comps = crud.get_all_competencies(db)
    comps_by_student: dict[str, list] = collections.defaultdict(list)
    for c in comps:
        if c.student_id in {s.student_id for s in students}:
            comps_by_student[c.student_id].append(c)
    result = []
    for s in students:
        comps = comps_by_student.get(s.student_id, [])
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
                    for c in sorted(comps, key=lambda c: c.competency_id)
                ],
            }
        )
    return result


def list_all_students(db: Session, instructor_user_id: int) -> list[dict]:
    """Section-scoped roster for the given instructor (no timeline payload)."""
    return _student_payloads(db, _scoped_students(db, instructor_user_id))


def is_student_in_scope(db: Session, instructor_user_id: int, student_id: str) -> bool:
    """True when the student is enrolled in a section the instructor teaches."""
    return any(s.student_id == student_id for s in _scoped_students(db, instructor_user_id))


def get_student_detail(db: Session, instructor_user_id: int, student_id: str) -> dict | None:
    """Return one student's full record (evidence timeline included), or
    ``None`` when the student doesn't exist or isn't in the instructor's
    sections."""
    if not is_student_in_scope(db, instructor_user_id, student_id):
        return None
    student = crud.get_student_by_id(db, student_id)
    if student is None:
        return None
    comps = crud.get_competencies(db, student_id)
    events = crud.list_evidence_events(db, student_id, newest_first=True)
    return {
        "student_id": student.student_id,
        "display_name": student.display_name,
        "course_code": student.course_code,
        "course_title": student.course_title,
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
        "evidence_timeline": [
            {
                "timestamp": e.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") if e.timestamp else "",
                "event_type": e.event_type,
                "competency_id": e.competency_id,
                "title": e.title,
                "detail": e.detail,
                "result": e.result,
            }
            for e in events
        ],
    }


def get_competency_aggregate(db: Session, instructor_user_id: int) -> list[dict]:
    """For each competency, count how many scoped students are at each status.

    Useful for the instructor dashboard: "12 demonstrated, 14 developing,
    6 needs_practice on PID Reasoning."
    """
    students = _scoped_students(db, instructor_user_id)
    if not students:
        return [
            {
                "competency_id": c["id"],
                "competency_name": c["name"],
                "demonstrated": 0,
                "developing": 0,
                "needs_practice": 0,
                "not_started": 0,
            }
            for c in INITIAL_COMPETENCIES
        ]
    student_ids = {s.student_id for s in students}
    comps = crud.get_all_competencies(db)
    comp_lookup = {(c.student_id, c.competency_id): c for c in comps if c.student_id in student_ids}
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
        for sid in student_ids:
            sc = comp_lookup.get((sid, c["id"]))
            if sc is None:
                continue
            if sc.status in row:
                row[sc.status] += 1
        rows.append(row)
    return rows


def get_class_summary(db: Session, instructor_user_id: int) -> dict:
    """High-level numbers for the instructor dashboard header (scoped)."""
    roster = _scoped_students(db, instructor_user_id)
    if not roster:
        return {
            "total_students": 0,
            "average_overall_progress": 0,
            "students_demonstrated_all": 0,
            "students_with_failures": 0,
        }
    payloads = _student_payloads(db, roster)
    return {
        "total_students": len(payloads),
        "average_overall_progress": (
            sum(s["overall_progress"] for s in payloads) // len(payloads) if payloads else 0
        ),
        "students_demonstrated_all": sum(
            1 for s in payloads if all(c["status"] == "demonstrated" for c in s["competencies"])
        ),
        "students_with_failures": sum(
            1 for s in payloads if any(c["status"] == "needs_practice" for c in s["competencies"])
        ),
    }
