"""Deterministic mastery rules applied to evidence histories."""

from typing import List

from pydantic import BaseModel, Field

from ai_education.domain.evidence import PracticalEvidence


class MasteryRuleConfig(BaseModel):
    """Configuration controlling when a competency node is formally mastered."""

    min_consecutive_passes: int = Field(default=2, ge=1)
    require_prerequisites_mastered: bool = False
    strict_overshoot_pct: float = Field(default=5.0, ge=0.0)


def count_consecutive_passes(evidence_list: List[PracticalEvidence]) -> int:
    """Count the trailing run of passing attempts in the evidence history."""
    count = 0
    for evidence in reversed(evidence_list):
        if not evidence.requirements_met:
            break
        count += 1
    return count


def check_evidence_consistency(
    evidence_list: List[PracticalEvidence], min_passes: int
) -> bool:
    """Return True when the history tail has at least ``min_passes`` passes.

    A tail is consistent only if every attempt from the most recent one back
    is a passing attempt — a failure anywhere in the tail resets the run.
    """
    return count_consecutive_passes(evidence_list) >= min_passes


def passes_strict_overshoot(
    evidence_list: List[PracticalEvidence], strict_overshoot_pct: float
) -> bool:
    """Return True when every evidence stays within the strict overshoot bound.

    A non-positive bound deactivates strict overshoot checking; an empty
    history is vacuously consistent.
    """
    if strict_overshoot_pct <= 0.0:
        return True
    return all(
        evidence.metrics.overshoot <= strict_overshoot_pct
        for evidence in evidence_list
    )