"""Schemas for admin-facing org management endpoints (Sprint 3).

These back the SUPER_ADMIN / UNIVERSITY_ADMIN provisioning API for the
University → Faculty → Department → Course → Section hierarchy and
student enrollment.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class UniversityCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    email_domains: list[str] = Field(default_factory=list)


class UniversityOut(BaseModel):
    id: int
    code: str
    name: str
    email_domains: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


class UniversityAdminCreate(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    university_code: str = Field(..., min_length=1, max_length=32)


class FacultyCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)


class FacultyOut(BaseModel):
    id: int
    university_id: int
    code: str
    name: str

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    faculty_id: int
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)


class DepartmentOut(BaseModel):
    id: int
    faculty_id: int
    code: str
    name: str

    model_config = {"from_attributes": True}


class CourseCreate(BaseModel):
    department_id: int
    code: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=255)
    credits: int = Field(default=3, ge=0, le=30)


class CourseOut(BaseModel):
    id: int
    department_id: int
    code: str
    title: str
    credits: int

    model_config = {"from_attributes": True}


class SectionCreate(BaseModel):
    course_id: int
    term: str = Field(..., description="e.g. 2026-S1")
    code: str = Field(..., max_length=32)
    instructor_user_id: int | None = None


class SectionOut(BaseModel):
    id: int
    course_id: int
    term: str
    code: str
    instructor_user_id: int | None

    model_config = {"from_attributes": True}


class InstructorCreate(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class StudentCreate(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    course_code: str = Field(default="MEC271", max_length=32)
    course_title: str = Field(default="Automatic Control", max_length=255)
    section_id: int | None = None

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.lower()


class EnrollmentRequest(BaseModel):
    student_id: str = Field(..., max_length=64)
    section_id: int


class EnrollmentOut(BaseModel):
    student_id: str
    section_id: int
    status: str

    model_config = {"from_attributes": True}


class OrgTreeOut(BaseModel):
    university_id: int
    university_code: str
    university_name: str
    faculties: list[dict]


class MessageOut(BaseModel):
    message: str


class AdminStudentOut(BaseModel):
    """One row in a section roster (admin view)."""

    student_id: str
    display_name: str
    course_code: str
    course_title: str
    overall_progress: int

    model_config = {"from_attributes": True}
