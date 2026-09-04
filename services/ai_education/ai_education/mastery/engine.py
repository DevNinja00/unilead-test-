"""Mastery determination: evaluate evidence and formal state transitions.

``MasteryDeterminationEngine`` evaluates a competency's evidence history for
conformance to ``MasteryRuleConfig`` and, when the criteria are met, promotes
the node to ``CompetencyState.MASTERED`` through the student model manager.
"""

from typing import List

from pydantic import BaseModel

from ai_education.domain.enums import CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.mastery.rules import (
    MasteryRuleConfig,
    count_consecutive_passes,
)


class MasteryEvaluationResult(BaseModel):
    """The verdict and rationale for one competency mastery evaluation."""

    student_id: str
    competency_id: str
    is_mastered: bool
    reason: str
    consecutive_passes: int


class MasteryDeterminationEngine:
    """Formally transitions nodes to MASTERED from consistent evidence."""

    @staticmethod
    def _prerequisite_alignment(
        manager: StudentModelManager, competency_id: str
    ) -> tuple[bool, List[str]]:
        """Return (all_parents_mastered, list_of_unmastered_parent_ids)."""
        node = manager.graph.get_node(competency_id)
        unmastered: List[str] = []
        for parent_id in node.parent_ids if node is not None else []:
            parent_record = manager.profile.competencies.get(parent_id)
            if (
                parent_record is None
                or parent_record.state != CompetencyState.MASTERED
            ):
                unmastered.append(parent_id)
        return not unmastered, unmastered

    def evaluate_mastery(
        self,
        student_id: str,
        competency_id: str,
        manager: StudentModelManager,
        config: MasteryRuleConfig = MasteryRuleConfig(),
    ) -> MasteryEvaluationResult:
        """Evaluate a competency and, if criteria are met, mark it MASTERED."""
        if manager.profile.student_id != student_id:
            raise ValueError(
                f"student_id {student_id!r} does not match manager profile "
                f"{manager.profile.student_id!r}"
            )
        if manager.graph.get_node(competency_id) is None:
            raise KeyError(f"Unknown competency node id: {competency_id!r}")

        record = manager.profile.competencies[competency_id]
        consecutive_passes = count_consecutive_passes(record.evidence_history)
        all_parents_mastered, unmastered_parents = self._prerequisite_alignment(
            manager, competency_id
        )

        passes_ok = consecutive_passes >= config.min_consecutive_passes
        prerequisites_ok = (
            not config.require_prerequisites_mastered
        ) or all_parents_mastered
        is_mastered = passes_ok and prerequisites_ok

        if is_mastered:
            record.state = CompetencyState.MASTERED
            reason = (
                f"Mastered: {consecutive_passes} consecutive pass(es) meet "
                f"the minimum of {config.min_consecutive_passes}."
            )
            if config.require_prerequisites_mastered:
                reason += " All prerequisites are mastered."
        else:
            reasons: List[str] = []
            if not passes_ok:
                reasons.append(
                    f"{consecutive_passes} consecutive pass(es) is below the "
                    f"minimum of {config.min_consecutive_passes}"
                )
            if config.require_prerequisites_mastered and not all_parents_mastered:
                reasons.append(
                    "prerequisites not mastered: "
                    + ", ".join(unmastered_parents)
                )
            reason = "Not mastered: " + "; ".join(reasons) + "."

        return MasteryEvaluationResult(
            student_id=student_id,
            competency_id=competency_id,
            is_mastered=is_mastered,
            reason=reason,
            consecutive_passes=consecutive_passes,
        )