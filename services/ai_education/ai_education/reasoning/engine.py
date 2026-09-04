"""Evidence reasoning: synthesize attempts and recommend the next coach mode.

``EvidenceReasoningEngine`` condenses a competency's ``PracticalEvidence``
history into an ``EvidenceReasoningSummary``: attempt counts, trailing
consecutive failures, the physical misconception behind the latest failure,
and a pedagogical next-mode recommendation.
"""

from typing import List

from pydantic import BaseModel, Field

from ai_education.domain.evidence import PracticalEvidence
from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning.misconceptions import (
    PIDMisconception,
    diagnose_misconception,
)
from ai_education.robotics.telemetry import StepResponseTelemetry

REMEDIATE_FAILURE_THRESHOLD = 2


class EvidenceReasoningSummary(BaseModel):
    """Synthesized understanding of one competency's evidence history."""

    competency_id: str
    total_attempts: int = Field(ge=0)
    consecutive_failures: int = Field(ge=0)
    detected_misconception: PIDMisconception = PIDMisconception.NONE
    recommended_mode: CoachMode
    summary_text: str


class EvidenceReasoningEngine:
    """Analyzes recorded evidence and recommends the next coach mode."""

    @staticmethod
    def _consecutive_failures(evidence_history: List[PracticalEvidence]) -> int:
        """Count trailing attempts that did not meet requirements."""
        count = 0
        for evidence in reversed(evidence_history):
            if evidence.requirements_met:
                break
            count += 1
        return count

    @staticmethod
    def _telemetry_from_evidence(
        evidence: PracticalEvidence,
    ) -> StepResponseTelemetry:
        """Reconstruct the telemetry reading behind a recorded evidence."""
        return StepResponseTelemetry(
            overshoot_pct=evidence.metrics.overshoot,
            settling_time_sec=evidence.metrics.settling_time,
            rise_time_sec=0.0,
            steady_state_error=evidence.metrics.steady_state_error,
            is_stable=evidence.stable,
        )

    def diagnose_latest_failure(
        self, evidence_history: List[PracticalEvidence]
    ) -> PIDMisconception:
        """Diagnose the misconception behind the most recent failing attempt."""
        for evidence in reversed(evidence_history):
            if not evidence.requirements_met:
                return diagnose_misconception(
                    self._telemetry_from_evidence(evidence)
                )
        return PIDMisconception.NONE

    @staticmethod
    def recommend_mode(
        state: CompetencyState,
        consecutive_failures: int,
        total_attempts: int,
    ) -> CoachMode:
        """Pick the pedagogical mode that best serves the learner next.

        Priority: repeated failures demand remediation; a demonstrated
        competency should be generalized (TRANSFER); untouched competencies
        start with LEARN; everything in between keeps practicing.
        """
        if consecutive_failures >= REMEDIATE_FAILURE_THRESHOLD:
            return CoachMode.REMEDIATE
        if state == CompetencyState.DEMONSTRATED:
            return CoachMode.TRANSFER
        if total_attempts == 0:
            return CoachMode.LEARN
        return CoachMode.PRACTICE

    def _compose_summary_text(
        self,
        competency_id: str,
        total_attempts: int,
        consecutive_failures: int,
        misconception: PIDMisconception,
        recommended_mode: CoachMode,
    ) -> str:
        if total_attempts == 0:
            return (
                f"Competency {competency_id} has no recorded attempts yet; "
                f"the next mode should be LEARN to introduce the material."
            )
        detail = (
            f"Competency {competency_id}: {total_attempts} attempt(s), "
            f"{consecutive_failures} consecutive failure(s)."
        )
        if misconception is not PIDMisconception.NONE:
            detail += (
                f" The latest failure suggests an "
                f"'{misconception.value.lower()}' misconception."
            )
        detail += f" The recommended next mode is {recommended_mode.value}."
        return detail

    def analyze_competency_evidence(
        self,
        student_id: str,
        competency_id: str,
        manager: StudentModelManager,
    ) -> EvidenceReasoningSummary:
        """Synthesize one competency's evidence into a reasoning summary."""
        if manager.profile.student_id != student_id:
            raise ValueError(
                f"student_id {student_id!r} does not match manager profile "
                f"{manager.profile.student_id!r}"
            )
        record = manager.profile.competencies.get(competency_id)
        evidence_history = list(record.evidence_history) if record else []
        total_attempts = len(evidence_history)
        consecutive_failures = self._consecutive_failures(evidence_history)
        misconception = self.diagnose_latest_failure(evidence_history)
        state = (
            record.state
            if record is not None
            else CompetencyState.NOT_DEMONSTRATED
        )
        recommended_mode = self.recommend_mode(
            state, consecutive_failures, total_attempts
        )
        return EvidenceReasoningSummary(
            competency_id=competency_id,
            total_attempts=total_attempts,
            consecutive_failures=consecutive_failures,
            detected_misconception=misconception,
            recommended_mode=recommended_mode,
            summary_text=self._compose_summary_text(
                competency_id,
                total_attempts,
                consecutive_failures,
                misconception,
                recommended_mode,
            ),
        )