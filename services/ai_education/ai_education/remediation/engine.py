"""Remediation engine: turn a diagnosed misconception into an action plan.

``RemediationEngine`` consumes the evidence reasoning for one competency and
produces a ``RemediationPlan`` whose ``RemediationAction``, ``guided_question``,
and ``remediation_steps`` are tailored to the exact physical failure mode.
"""

from typing import List

from pydantic import BaseModel, Field

from ai_education.domain.enums import CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning.engine import EvidenceReasoningEngine
from ai_education.reasoning.misconceptions import PIDMisconception
from ai_education.remediation.strategies import (
    RemediationAction,
    get_remediation_strategy,
)


class RemediationPlan(BaseModel):
    """A structured plan that isolates a specific physical failure."""

    student_id: str
    competency_id: str
    misconception: PIDMisconception
    action: RemediationAction
    guided_question: str
    remediation_steps: List[str] = Field(min_length=1)


class RemediationEngine:
    """Builds targeted micro-interventions for diagnosed misconceptions."""

    @staticmethod
    def _prerequisite_gaps(
        manager: StudentModelManager, competency_id: str
    ) -> List[str]:
        """Return the undemonstrated prerequisite ids, oldest-first."""
        node = manager.graph.get_node(competency_id)
        if node is None:
            return []
        gaps: List[str] = []
        for dependency_id in node.parent_ids:
            dep_record = manager.profile.competencies.get(dependency_id)
            if dep_record is None or dep_record.state != CompetencyState.DEMONSTRATED:
                gaps.append(dependency_id)
        return gaps

    def _compose_steps(
        self,
        misconception: PIDMisconception,
        strategy: dict,
        prerequisite_gaps: List[str],
    ) -> List[str]:
        """Construct remediation steps for the specific failure mode."""
        action = strategy["action"]
        steps: List[str] = []
        if misconception is PIDMisconception.UNSTABLE_TUNING:
            steps = [
                "Reset the PID gains to a known-stable baseline.",
                "Re-run the step response and confirm a bounded, converging output.",
                "Reintroduce gains one term at a time, watching for oscillation.",
                "Record the gain values at which the system became unstable.",
            ]
            if prerequisite_gaps:
                steps.insert(0, "Review stability fundamentals before retuning.")
                steps.append(
                    "Pass the prerequisite competencies "
                    + ", ".join(prerequisite_gaps)
                    + " before advancing."
                )
        elif misconception is PIDMisconception.MISSING_INTEGRAL_ACTION:
            steps = [
                "Explain why proportional-only control leaves steady-state error.",
                "Add an integral term with a small Ki.",
                "Increase Ki gradually until the steady-state error closes to zero.",
                "Watch for overshoot introduced by a growing integral term.",
            ]
        elif misconception is PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN:
            steps = [
                "Trace how Kp trades rise time against overshoot.",
                "Reduce Kp in small steps until overshoot fits within the tolerance.",
                "Re-check that rise time remains acceptable after lowering Kp.",
            ]
        elif misconception is PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING:
            steps = [
                "Explain why the tail oscillates when derivative action is weak.",
                "Increase Kd in small steps to damp the settling tail.",
                "Verify the response still settles promptly at the new Kd.",
            ]
        else:
            steps = [
                "Review the step response plot against the pass criteria.",
                "Re-confirm each gain's role in the response trace.",
                "Re-run the tuning and compare against the previous attempt.",
            ]
        return steps

    def build_remediation_plan(
        self,
        student_id: str,
        competency_id: str,
        manager: StudentModelManager,
        reasoning_engine: EvidenceReasoningEngine,
    ) -> RemediationPlan:
        """Build the remediation plan for the given competency."""
        if manager.graph.get_node(competency_id) is None:
            raise KeyError(f"Unknown competency node id: {competency_id!r}")
        summary = reasoning_engine.analyze_competency_evidence(
            student_id, competency_id, manager
        )
        misconception = summary.detected_misconception
        strategy = get_remediation_strategy(misconception)
        prerequisite_gaps = self._prerequisite_gaps(manager, competency_id)
        steps = self._compose_steps(misconception, strategy, prerequisite_gaps)
        return RemediationPlan(
            student_id=student_id,
            competency_id=competency_id,
            misconception=misconception,
            action=RemediationAction(strategy["action"]),
            guided_question=str(strategy["diagnostic_question"]),
            remediation_steps=steps,
        )