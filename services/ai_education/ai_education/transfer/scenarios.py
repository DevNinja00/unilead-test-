"""Cross-domain transfer scenarios used by transfer assessment.

Each scenario re-maps the same PID tuning principles — the error signal, the
control output, and the system inertia — onto a different physical plant.
That forces the student to reason from the underlying control concept rather
than recalling the motor-speed example verbatim. ``TRANSFER_DOMAIN_TERMS``
carries the qualitative vocabulary per domain that ``TransferAssessmentEngine``
uses to judge the student's explanation.
"""

from typing import Dict, List, Set

from pydantic import BaseModel


class TransferScenario(BaseModel):
    """A structured cross-domain challenge bridging PID control to a new plant."""

    scenario_id: str
    title: str
    domain: str
    error_signal_meaning: str
    control_output_meaning: str
    system_inertia: str
    conceptual_challenge: str


TRANSFER_DOMAIN_TERMS: Dict[str, Set[str]] = {
    "industrial_oven": {
        "thermal inertia",
        "delay",
        "accumulation",
        "temperature",
    },
    "water_tank_level": {
        "accumulation",
        "inflow",
        "outflow",
        "level",
    },
    "quadrotor_pitch": {
        "thrust",
        "torque",
        "attitude",
        "pitch",
    },
}


def get_transfer_scenarios() -> List[TransferScenario]:
    """Return the pre-populated cross-domain transfer scenarios."""
    return [
        TransferScenario(
            scenario_id="industrial_oven",
            title="PID control of an industrial oven",
            domain="thermal",
            error_signal_meaning=(
                "The difference between the target oven temperature and the "
                "measured chamber temperature."
            ),
            control_output_meaning=(
                "The burner power commanded to add or reduce heat in the chamber."
            ),
            system_inertia=(
                "Thermal inertia: the chamber stores heat, so temperature "
                "changes lag the burner power."
            ),
            conceptual_challenge=(
                "Explain how Kp, Ki, and Kd each behave under thermal inertia "
                "and heating delay."
            ),
        ),
        TransferScenario(
            scenario_id="water_tank_level",
            title="PID control of a water tank level",
            domain="fluid",
            error_signal_meaning=(
                "The difference between the target water level and the "
                "measured level in the tank."
            ),
            control_output_meaning=(
                "The inlet valve opening that drives the water inflow."
            ),
            system_inertia=(
                "The tank's volume integrates inflow: level accumulates over "
                "time as water streams in."
            ),
            conceptual_challenge=(
                "Explain how the integral term closes the level error when "
                "outflow keeps draining the tank."
            ),
        ),
        TransferScenario(
            scenario_id="quadrotor_pitch",
            title="PID control of a quadrotor's pitch attitude",
            domain="aerospace",
            error_signal_meaning=(
                "The difference between the commanded pitch angle and the "
                "attitude measured by the IMU."
            ),
            control_output_meaning=(
                "The differential motor thrust that applies a pitching torque."
            ),
            system_inertia=(
                "The rotor acceleration delay and the body's rotational "
                "inertia dominate the response."
            ),
            conceptual_challenge=(
                "Explain how derivative action damps pitch overshoot when the "
                "rotors respond at time scale."
            ),
        ),
    ]


def get_transfer_scenario(scenario_id: str) -> TransferScenario:
    """Return the scenario with the given id, raising ``KeyError`` if absent."""
    for scenario in get_transfer_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario
    raise KeyError(f"Unknown transfer scenario id: {scenario_id!r}")