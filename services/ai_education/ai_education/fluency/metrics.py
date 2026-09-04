"""AI-fluency metrics: quantify prompt specificity and critical verification.

``FluencyLevel`` buckets an overall fluency score into coarse proficiency
bands. ``compute_prompt_specificity`` and ``extract_technical_signals`` turn a
student's free-text prompt into deterministic, reproducible measurements of
how much engineering detail (gains, constraints, units) it actually carries.
"""

import re
from enum import Enum
from typing import List, Tuple

from pydantic import BaseModel, Field


class FluencyLevel(str, Enum):
    """Proficiency band for a student's AI-collaboration fluency."""

    NOVICE = "NOVICE"
    COMPETENT = "COMPETENT"
    PROFICIENT = "PROFICIENT"
    EXPERT = "EXPERT"


TECHNICAL_PARAMETER_SIGNALS: Tuple[Tuple[str, str], ...] = (
    ("Kp", r"k[_ ]?p"),
    ("Ki", r"k[_ ]?i"),
    ("Kd", r"k[_ ]?d"),
    ("settling time", r"settling[ _-]?time"),
    ("overshoot", r"overshoot"),
    ("rise time", r"rise[ _-]?time"),
    ("steady-state error", r"steady[ _-]?state[ _-]?error"),
    ("setpoint", r"setpoint|set[ _-]?point"),
)

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


class AIFluencyMetrics(BaseModel):
    """Snapshot of one student's AI-collaboration fluency dimensions."""

    prompt_quality_score: float = Field(ge=0.0, le=1.0)
    critical_verification_score: float = Field(ge=0.0, le=1.0)
    autonomy_score: float = Field(ge=0.0, le=1.0)
    overall_fluency_score: float = Field(ge=0.0, le=1.0)
    fluency_level: FluencyLevel


def extract_technical_signals(prompt_text: str) -> List[str]:
    """Return the canonical technical signals present in a prompt (case-free)."""
    normalized = prompt_text.lower()
    return [
        signal_name
        for signal_name, pattern in TECHNICAL_PARAMETER_SIGNALS
        if re.search(pattern, normalized) is not None
    ]


def compute_prompt_specificity(prompt_text: str) -> float:
    """Fraction of the canonical technical signal set covered by the prompt."""
    matched = len(extract_technical_signals(prompt_text))
    return round(matched / len(TECHNICAL_PARAMETER_SIGNALS), 3)


def contains_numeric_value(prompt_text: str) -> bool:
    """Return True when the prompt states an explicit numeric value."""
    return _NUMBER_PATTERN.search(prompt_text) is not None


def score_fluency_level(overall_fluency_score: float) -> FluencyLevel:
    """Map an overall fluency score onto the discrete FluencyLevel bands."""
    if overall_fluency_score >= 0.85:
        return FluencyLevel.EXPERT
    if overall_fluency_score >= 0.7:
        return FluencyLevel.PROFICIENT
    if overall_fluency_score >= 0.5:
        return FluencyLevel.COMPETENT
    return FluencyLevel.NOVICE