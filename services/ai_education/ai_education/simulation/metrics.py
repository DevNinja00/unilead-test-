"""Deterministic step-response metric extraction.

Reduces a closed-loop trajectory into the five telemetry quantities the
rest of the platform reasons over: overshoot %, settling time, rise time,
steady-state error, and a stability flag derived from an envelope-growth
test (a limit cycle or diverging oscillation is unstable).
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class StepMetrics:
    """Extracted telemetry quantities for one simulated step response."""

    overshoot_pct: float
    settling_time_sec: float
    rise_time_sec: float
    steady_state_error: float
    is_stable: bool


DEFAULT_SETTLE_BAND_FRACTION = 0.02


def _within_band(deviation: float, band: float) -> bool:
    return deviation <= band


def extract_step_metrics(
    times: List[float],
    output: List[float],
    setpoint: float,
    settle_band_fraction: float = DEFAULT_SETTLE_BAND_FRACTION,
) -> StepMetrics:
    """Compute ``StepMetrics`` from a sampled closed-loop trajectory."""
    if setpoint <= 0:
        raise ValueError("setpoint must be positive")
    n = len(output)
    if n == 0:
        raise ValueError("output must contain at least one sample")

    band = settle_band_fraction * setpoint
    deviations = [abs(y - setpoint) for y in output]

    peak = max(output)
    overshoot_pct = (
        (peak - setpoint) / setpoint * 100.0 if peak > setpoint else 0.0
    )

    rise_time_sec = _rise_time(times, output, setpoint)
    settling_time_sec = _settling_time(times, deviations, band)
    steady_state_error = _steady_state_error(deviations)
    is_stable = _is_stable(times, output, setpoint, band)

    return StepMetrics(
        overshoot_pct=overshoot_pct,
        settling_time_sec=settling_time_sec,
        rise_time_sec=rise_time_sec,
        steady_state_error=steady_state_error,
        is_stable=is_stable,
    )


def _rise_time(
    times: List[float], output: List[float], setpoint: float
) -> float:
    """Time between the first 10% and first 90% crossings of setpoint."""
    ten_index: int | None = None
    ninety_index: int | None = None
    for i, y in enumerate(output):
        if ten_index is None and y >= 0.1 * setpoint:
            ten_index = i
        if ninety_index is None and y >= 0.9 * setpoint:
            ninety_index = i
    if (
        ten_index is not None
        and ninety_index is not None
        and ninety_index > ten_index
    ):
        return float(times[ninety_index] - times[ten_index])
    return float(times[-1])


def _settling_time(
    times: List[float], deviations: List[float], band: float
) -> float:
    """First time from which the response stays within the band forever."""
    for i in range(len(deviations)):
        if all(_within_band(d, band) for d in deviations[i:]):
            return float(times[i])
    return float(times[-1])


def _steady_state_error(deviations: List[float]) -> float:
    """Mean absolute deviation over the final 10% of the response."""
    n = len(deviations)
    tail = deviations[int(n * 0.9) :] or deviations
    return sum(tail) / len(tail)


def _is_stable(
    times: List[float],
    output: List[float],
    setpoint: float,
    band: float,
) -> bool:
    """Stability via a tail-decay + oscillation test.

    A bounded plant under a clamped actuator cannot diverge to infinity, so
    a "real" instability is a *sustained limit cycle*: the post-transient
    output keeps oscillating across the setpoint at an amplitude that never
    decays back inside the regulation band. A constant steady-state offset
    (proportional-only control) is physically stable, so a flat, sign-frozen
    tail is *not* treated as instability - the response is only unstable when
    the tail both fails to decay and keeps crossing the setpoint.
    """
    n = len(times)
    if n < 24:
        return True
    middle = output[int(n * 0.4) : int(n * 0.7)] or output
    tail = output[int(n * 0.7) :] or output
    middle_deviation_max = max(abs(y - setpoint) for y in middle)
    tail_deviation_max = max(abs(y - setpoint) for y in tail)
    if tail_deviation_max <= band:
        return True
    if tail_deviation_max < 0.7 * middle_deviation_max:
        return True
    return not _oscillates_across_setpoint(tail, setpoint)


def _oscillates_across_setpoint(output: List[float], setpoint: float) -> bool:
    """True when the output keeps crossing the setpoint (sign changes)."""
    sign_changes = 0
    previous_sign: int | None = None
    for y in output:
        delta = y - setpoint
        sign = 0 if delta == 0 else (1 if delta > 0 else -1)
        if sign != 0:
            if previous_sign is not None and sign != previous_sign:
                sign_changes += 1
            previous_sign = sign
    return sign_changes >= 4