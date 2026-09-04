"""Evidence reasoning: evidence synthesis and pedagogical recommendations."""

from ai_education.reasoning.engine import (
    EvidenceReasoningEngine,
    EvidenceReasoningSummary,
)
from ai_education.reasoning.misconceptions import (
    PIDMisconception,
    diagnose_misconception,
)

__all__ = [
    "EvidenceReasoningEngine",
    "EvidenceReasoningSummary",
    "PIDMisconception",
    "diagnose_misconception",
]