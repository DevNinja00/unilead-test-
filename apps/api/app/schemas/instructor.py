"""Schemas for instructor-facing endpoints.

These are intentionally simple read-only views over the student registry.
No write operations are exposed here — instructors look, they don't touch.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class InstructorStudentSummary(BaseModel):
    """One row in the instructor's student roster."""

    student_id: str
    display_name: str
    course_code: str
    course_title: str
    overall_progress: int
    competencies: list[dict] = Field(
        ..., description="Compact list of {id, name, status, progress}."
    )


class InstructorCompetencyAggregate(BaseModel):
    """Per-competency counts across the class."""

    competency_id: str
    competency_name: str
    demonstrated: int
    developing: int
    needs_practice: int
    not_started: int


class InstructorClassSummary(BaseModel):
    """High-level numbers for the instructor dashboard header."""

    total_students: int
    average_overall_progress: int
    students_demonstrated_all: int = Field(
        ..., description="Students who've demonstrated every competency."
    )
    students_with_failures: int = Field(
        ..., description="Students with at least one needs_practice competency."
    )


class EvidenceEvent(BaseModel):
    """One event on a student's evidence timeline."""

    timestamp: str = Field(..., description="RFC3339 UTC timestamp.")
    event_type: str = Field(
        ..., description="diagnostic_submitted / simulation_run / remediation_completed / transfer_evaluated / coach_turn."
    )
    competency_id: Optional[str] = None
    title: str
    detail: str
    result: str = Field(..., description="PASS / FAIL / INFO.")


class InstructorStudentDetail(BaseModel):
    """A single student's full instructor-facing record."""

    student_id: str
    display_name: str
    course_code: str
    course_title: str
    overall_progress: int
    competencies: list[dict]
    evidence_timeline: list[EvidenceEvent]
