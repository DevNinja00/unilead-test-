"""Diagnosis of physical PID tuning misconceptions from step-response metrics.

The misconception rules mirror the physical symptoms of common tuning
mistakes, evaluated in a fixed priority order (the most severe symptom wins):

1. an unstable system -> the tuning is wildly out of range;
2. a residual steady-state error -> integral action is missing;
3. pronounced overshoot -> the proportional gain is too high;
4. a long settled tail with overshoot -> derivative damping is insufficient;
5. otherwise no misconception is flagged.
"""

from enum import Enum

from ai_education.robotics.telemetry import StepResponseTelemetry

MAX_ACCEPTABLE_STEADY_STATE_ERROR = 0.05
MAX_ACCEPTABLE_OVERSHOOT_PCT = 25.0
MAX_ACCEPTABLE_SETTLING_TIME_SEC = 2.0


class PIDMisconception(str, Enum):
    """Physical tuning misconceptions identifiable from telemetry."""

    EXCESSIVE_PROPORTIONAL_GAIN = "EXCESSIVE_PROPORTIONAL_GAIN"
    MISSING_INTEGRAL_ACTION = "MISSING_INTEGRAL_ACTION"
    INSUFFICIENT_DERIVATIVE_DAMPING = "INSUFFICIENT_DERIVATIVE_DAMPING"
    UNSTABLE_TUNING = "UNSTABLE_TUNING"
    NONE = "NONE"


def diagnose_misconception(telemetry: StepResponseTelemetry) -> PIDMisconception:
    """Diagnose the most likely tuning misconception from one telemetry reading."""
    if not telemetry.is_stable:
        return PIDMisconception.UNSTABLE_TUNING
    if telemetry.steady_state_error > MAX_ACCEPTABLE_STEADY_STATE_ERROR:
        return PIDMisconception.MISSING_INTEGRAL_ACTION
    if telemetry.overshoot_pct > MAX_ACCEPTABLE_OVERSHOOT_PCT:
        return PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN
    if (
        telemetry.settling_time_sec > MAX_ACCEPTABLE_SETTLING_TIME_SEC
        and telemetry.overshoot_pct > 0.0
    ):
        return PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING
    return PIDMisconception.NONE