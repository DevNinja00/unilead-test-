from pydantic import BaseModel

from .common import CompetencyStatus


class ProgressCompetency(BaseModel):
    """The lightweight competency shape used in the progress summary."""

    name: str
    status: CompetencyStatus


class ProgressResponse(BaseModel):
    overall_progress: int
    competencies: list[ProgressCompetency]
    recommended_next_activity: str
    course_code: str
    course_title: str
