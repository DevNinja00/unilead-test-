from pydantic import BaseModel

from .common import CompetencyStatus


class EvidenceItem(BaseModel):
    id: str
    label: str
    met: bool


class ReviewRequest(BaseModel):
    competency_id: str | None = None
    # False (default): just return the current evidence for display.
    # True: also fold the evidence back into the student's progress —
    # mirrors the "Continue to Progress" action in the UI.
    finalize: bool = False


class ReviewResponse(BaseModel):
    competency_id: str
    competency_name: str
    status: CompetencyStatus
    progress: int
    overall_progress: int
    evidence: list[EvidenceItem]
