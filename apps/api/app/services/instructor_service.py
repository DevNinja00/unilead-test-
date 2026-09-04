"""Instructor service — aggregate views over the student registry.

The instructor UI needs:
  - A list of all students with their overall progress + competency snapshots.
  - An aggregate per-competency view: how many students are demonstrated vs
    developing vs needs_practice vs not_started.
  - A single student's full record including their evidence timeline.

All data comes from ``student_state`` (the multi-student registry) — no
LLM, no AI in this layer.
"""

from __future__ import annotations

from . import student_state


def list_all_students() -> list[dict]:
    """Return a roster of every student (no timeline payload — too heavy)."""
    return student_state.list_students()


def get_student_detail(student_id: str) -> dict | None:
    """Return one student's full record including evidence timeline."""
    return student_state.get_student_by_id(student_id)


def get_competency_aggregate() -> list[dict]:
    """For each competency, count how many students are at each status.

    Useful for the instructor dashboard: "12 demonstrated, 14 developing,
    6 needs_practice on PID Reasoning."
    """
    return student_state.get_aggregate_by_competency()


def get_class_summary() -> dict:
    """High-level numbers for the instructor dashboard header."""
    students = student_state.list_students()
    return {
        "total_students": len(students),
        "average_overall_progress": (
            sum(s["overall_progress"] for s in students) // len(students)
            if students
            else 0
        ),
        "students_demonstrated_all": sum(
            1
            for s in students
            if all(c["status"] == "demonstrated" for c in s["competencies"])
        ),
        "students_with_failures": sum(
            1
            for s in students
            if any(c["status"] == "needs_practice" for c in s["competencies"])
        ),
    }
