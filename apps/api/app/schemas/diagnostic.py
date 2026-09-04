from pydantic import BaseModel, Field

from .common import CompetencyStatus


class DiagnosticOption(BaseModel):
    id: str
    label: str


class DiagnosticQuestion(BaseModel):
    id: str
    competency_id: str
    prompt: str
    options: list[DiagnosticOption]


class DiagnosticAnswer(BaseModel):
    question_id: str
    option_id: str


class DiagnosticSubmission(BaseModel):
    answers: list[DiagnosticAnswer]


class DiagnosticResult(BaseModel):
    competency_id: str
    competency_name: str
    status: CompetencyStatus
    # New: misconceptions detected from incorrect answers on this competency's
    # diagnostic question. Empty list if the student answered correctly.
    misconceptions: list[str] = Field(default_factory=list)
    # New: raw correctness on this competency's diagnostic question (0..1).
    accuracy: float = Field(default=0.0)
