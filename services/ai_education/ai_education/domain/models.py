"""Core domain models for competency tracking (MEC271)."""

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field

from ai_education.domain.enums import CompetencyState
from ai_education.domain.evidence import PracticalEvidence


class CompetencyNode(BaseModel):
    """A skill unit in the course competency graph (e.g. 'PID Tuning')."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str = ""
    parent_ids: List[str] = Field(
        default_factory=list,
        description="IDs of prerequisite competency nodes.",
    )


class CompetencyRecord(BaseModel):
    """Tracks a learner's status for a single competency unit."""

    model_config = ConfigDict(validate_assignment=True)

    competency_id: str
    state: CompetencyState = CompetencyState.NOT_DEMONSTRATED
    evidence_history: List[PracticalEvidence] = Field(default_factory=list)

    def record_evidence(self, evidence: PracticalEvidence) -> CompetencyState:
        """Append evidence and recompute the competency state.

        State progression rule: no passing attempts -> NOT_DEMONSTRATED,
        exactly one passing attempt -> DEVELOPING, two or more passing
        attempts -> DEMONSTRATED. Formally MASTERED competencies are sticky
        and never regress from further evidence.
        """
        if self.state == CompetencyState.MASTERED:
            return CompetencyState.MASTERED
        self.evidence_history.append(evidence)
        passing_attempts = sum(
            1 for ev in self.evidence_history if ev.requirements_met
        )
        if passing_attempts <= 0:
            self.state = CompetencyState.NOT_DEMONSTRATED
        elif passing_attempts == 1:
            self.state = CompetencyState.DEVELOPING
        else:
            self.state = CompetencyState.DEMONSTRATED
        return self.state


class StudentProfile(BaseModel):
    """A learner's competency snapshot for a course (default: MEC271)."""

    model_config = ConfigDict()

    student_id: str
    course_id: str = "MEC271"
    competencies: Dict[str, CompetencyRecord] = Field(default_factory=dict)