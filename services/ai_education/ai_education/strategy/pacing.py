"""Student learning-pace and scaffolding-level evaluation.

Pace and scaffolding are derived deterministically from a student's attempt
and failure statistics so downstream strategy generation is reproducible.
"""

from enum import Enum


class LearningPace(str, Enum):
    """Overall rate at which a student is mastering competencies."""

    FAST = "FAST"
    NORMAL = "NORMAL"
    STRUGGLING = "STRUGGLING"


class ScaffoldingLevel(str, Enum):
    """How much pedagogical support the student currently needs."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


STRUGGLING_FAILURE_RATE_THRESHOLD = 0.5
STRUGGLING_CONSECUTIVE_FAILURES = 2
FAST_ATTEMPTS_PER_COMPETENCY = 1
FAST_MAX_FAILURE_RATE = 0.0


def evaluate_pace(
    *,
    total_attempts: int,
    total_failures: int,
    competencies_attempted: int,
    consecutive_failures: int = 0,
) -> LearningPace:
    """Classify pace from aggregate failure rate and attempt frequency.

    - STRUGGLING: failure rate >= 0.5, or two or more consecutive failures.
    - FAST: at most one attempt per competency with zero failures.
    - otherwise NORMAL.
    """
    if total_attempts == 0:
        return LearningPace.NORMAL
    failure_rate = total_failures / total_attempts
    if failure_rate >= STRUGGLING_FAILURE_RATE_THRESHOLD:
        return LearningPace.STRUGGLING
    if consecutive_failures >= STRUGGLING_CONSECUTIVE_FAILURES:
        return LearningPace.STRUGGLING
    if (
        competencies_attempted > 0
        and total_attempts <= competencies_attempted * FAST_ATTEMPTS_PER_COMPETENCY
        and total_failures <= FAST_MAX_FAILURE_RATE
    ):
        return LearningPace.FAST
    return LearningPace.NORMAL


def evaluate_scaffolding_level(pace: LearningPace) -> ScaffoldingLevel:
    """Map a learning pace onto a scaffolding level."""
    if pace is LearningPace.STRUGGLING:
        return ScaffoldingLevel.HIGH
    if pace is LearningPace.FAST:
        return ScaffoldingLevel.LOW
    return ScaffoldingLevel.MEDIUM