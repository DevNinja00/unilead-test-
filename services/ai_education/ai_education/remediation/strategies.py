"""Targeted remediation strategies for diagnosed physical misconceptions."""

from enum import Enum
from typing import Dict

from ai_education.reasoning.misconceptions import PIDMisconception


class RemediationAction(str, Enum):
    """The concrete pedagogical intervention a misconception calls for."""

    EXPLAIN_CONCEPT = "EXPLAIN_CONCEPT"
    ADJUST_PARAMETER_STEP = "ADJUST_PARAMETER_STEP"
    REVIEW_PREREQUISITE = "REVIEW_PREREQUISITE"
    RESET_EXPERIMENT = "RESET_EXPERIMENT"


_STRATEGY_TABLE: Dict[PIDMisconception, Dict[str, str]] = {
    PIDMisconception.UNSTABLE_TUNING: {
        "action": RemediationAction.RESET_EXPERIMENT,
        "conceptual_focus": (
            "Tuning stability: gains outside the stable region cause runaway response."
        ),
        "diagnostic_question": (
            "At what gain values did the response become unstable, and what does "
            "that boundary tell you about the stability margin?"
        ),
    },
    PIDMisconception.MISSING_INTEGRAL_ACTION: {
        "action": RemediationAction.EXPLAIN_CONCEPT,
        "conceptual_focus": (
            "Integral action: steady-state error persists when the integral term "
            "cannot accumulate to close the loop."
        ),
        "diagnostic_question": (
            "Why does a proportional-only controller leave a steady-state error, "
            "and what would the integral term add to eliminate it?"
        ),
    },
    PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN: {
        "action": RemediationAction.ADJUST_PARAMETER_STEP,
        "conceptual_focus": (
            "Proportional gain: excessive Kp amplifies overshoot at the expense "
            "of a fast, calm response."
        ),
        "diagnostic_question": (
            "How does raising Kp shrink rise time at the cost of overshoot, and "
            "how would you tune it back toward a damped response?"
        ),
    },
    PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING: {
        "action": RemediationAction.REVIEW_PREREQUISITE,
        "conceptual_focus": (
            "Derivative damping: insufficient Kd leaves a slow oscillatory tail "
            "after the initial overshoot."
        ),
        "diagnostic_question": (
            "Why does derivative action damp the tail of a step response, and "
            "what happens when derivative gain is too small?"
        ),
    },
    PIDMisconception.NONE: {
        "action": RemediationAction.EXPLAIN_CONCEPT,
        "conceptual_focus": (
            "General tuning fundamentals: no specific misconception detected."
        ),
        "diagnostic_question": (
            "What trade-offs do you weigh when choosing proportional, integral, "
            "and derivative gains?"
        ),
    },
}


def get_remediation_strategy(
    misconception: PIDMisconception,
) -> Dict[str, str]:
    """Return the remediation strategy for a misconception.

    Maps the misconception to its action, conceptual focus, and a suggested
    diagnostic question. Returns the general strategy when ``NONE``.
    """
    return dict(_STRATEGY_TABLE[misconception])