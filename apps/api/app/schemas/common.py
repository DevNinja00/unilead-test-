from enum import StrEnum

from pydantic import BaseModel


class CompetencyStatus(StrEnum):
    not_started = "not_started"
    needs_practice = "needs_practice"
    developing = "developing"
    demonstrated = "demonstrated"


class Competency(BaseModel):
    """A single competency with its current mastery status and progress."""

    id: str
    name: str
    status: CompetencyStatus
    progress: int  # 0-100
