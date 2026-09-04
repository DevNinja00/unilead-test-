"""Enumerations for the AI/Education competency domain."""

from enum import Enum


class CompetencyState(str, Enum):
    """Learner's current mastery state for a single competency unit."""

    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
    DEVELOPING = "DEVELOPING"
    DEMONSTRATED = "DEMONSTRATED"
    MASTERED = "MASTERED"


class EvidenceType(str, Enum):
    """Source category of evidence that informs a competency record."""

    DIAGNOSTIC_QUIZ = "DIAGNOSTIC_QUIZ"
    PRACTICAL_SIMULATION = "PRACTICAL_SIMULATION"
    CONCEPTUAL_EXPLANATION = "CONCEPTUAL_EXPLANATION"
    TRANSFER_TASK = "TRANSFER_TASK"


class CoachMode(str, Enum):
    """Interaction modes the AI Coach can operate in."""

    LEARN = "LEARN"
    HINT = "HINT"
    PRACTICE = "PRACTICE"
    REFLECT = "REFLECT"
    REMEDIATE = "REMEDIATE"
    TRANSFER = "TRANSFER"