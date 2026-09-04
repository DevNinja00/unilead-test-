"""Adaptive strategy: aggregate the learner into an actionable plan.

``AdaptiveStrategyEngine`` combines the competency-state summary with the
evidence reasoning from ``EvidenceReasoningEngine`` to derive the student's
learning pace, scaffolding level, and the next pedagogical move.
"""

from typing import List, Optional

from pydantic import BaseModel

from ai_education.domain.enums import CoachMode
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning.engine import EvidenceReasoningEngine
from ai_education.strategy.pacing import (
    LearningPace,
    ScaffoldingLevel,
    evaluate_pace,
    evaluate_scaffolding_level,
)


class AdaptiveStrategyPlan(BaseModel):
    """A deterministic, per-student adaptive learning strategy."""

    student_id: str
    current_pace: LearningPace
    scaffolding_level: ScaffoldingLevel
    recommended_target_node_id: Optional[str] = None
    recommended_mode: CoachMode
    strategy_notes: str


class AdaptiveStrategyEngine:
    """Builds an adaptive strategy plan from the manager and reasoning engine."""

    @staticmethod
    def _aggregate_attempt_stats(
        manager: StudentModelManager,
    ) -> tuple[int, int, int]:
        """Return (total_attempts, total_failures, competencies_attempted)."""
        total_attempts = 0
        total_failures = 0
        competencies_attempted = 0
        for record in manager.profile.competencies.values():
            history = record.evidence_history
            if history:
                competencies_attempted += 1
                total_attempts += len(history)
                total_failures += sum(
                    1 for ev in history if not ev.requirements_met
                )
        return total_attempts, total_failures, competencies_attempted

    def recommend_mode(
        self,
        manager: StudentModelManager,
        reasoning_engine: EvidenceReasoningEngine,
        target: Optional[object],
        pace: LearningPace,
    ) -> CoachMode:
        """Pick the recommended coach mode for the plan.

        A struggling learner targeting one competency gets remediated when
        there are repeated failures; otherwise the target's own reasoning
        summary drives the choice.
        """
        target_id = target.id if target is not None else None
        state_summary = manager.get_summary()
        demonstrated = int(state_summary["demonstrated_count"])
        total = int(state_summary["total_competencies"])

        if target_id is not None:
            summary = reasoning_engine.analyze_competency_evidence(
                manager.profile.student_id, target_id, manager
            )
            return summary.recommended_mode
        if demonstrated >= total:
            return CoachMode.REFLECT
        return CoachMode.LEARN

    def generate_strategy_plan(
        self,
        student_id: str,
        manager: StudentModelManager,
        reasoning_engine: EvidenceReasoningEngine,
    ) -> AdaptiveStrategyPlan:
        """Generate the adaptive strategy plan for the given student."""
        if manager.profile.student_id != student_id:
            raise ValueError(
                f"student_id {student_id!r} does not match manager profile "
                f"{manager.profile.student_id!r}"
            )
        total_attempts, total_failures, competencies_attempted = (
            self._aggregate_attempt_stats(manager)
        )
        target = manager.get_next_target_competency()
        consecutive_failures = 0
        if target is not None:
            summary = reasoning_engine.analyze_competency_evidence(
                student_id, target.id, manager
            )
            consecutive_failures = summary.consecutive_failures
        pace = evaluate_pace(
            total_attempts=total_attempts,
            total_failures=total_failures,
            competencies_attempted=competencies_attempted,
            consecutive_failures=consecutive_failures,
        )
        scaffolding = evaluate_scaffolding_level(pace)
        mode = self.recommend_mode(manager, reasoning_engine, target, pace)
        notes = self._compose_notes(
            manager, pace, scaffolding, target, total_attempts, total_failures
        )
        return AdaptiveStrategyPlan(
            student_id=student_id,
            current_pace=pace,
            scaffolding_level=scaffolding,
            recommended_target_node_id=target.id if target else None,
            recommended_mode=mode,
            strategy_notes=notes,
        )

    @staticmethod
    def _compose_notes(
        manager: StudentModelManager,
        pace: LearningPace,
        scaffolding: ScaffoldingLevel,
        target: Optional[object],
        total_attempts: int,
        total_failures: int,
    ) -> str:
        target_id = target.id if target is not None else None
        base = (
            f"Pace is {pace.value} with {scaffolding.value} scaffolding across "
            f"{total_attempts} attempt(s) and {total_failures} failure(s)."
        )
        if target_id is not None:
            base += (
                f" Focus learning on competency {target_id} with "
                f"{scaffolding.value}-level support."
            )
        else:
            base += " All competencies are demonstrated; reinforce with reflection."
        return base