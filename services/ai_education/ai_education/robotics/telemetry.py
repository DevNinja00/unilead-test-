"""Robotics simulation telemetry schemas.

These models describe the raw step-response payload that a robotics
simulator emits after each practical run. They stay free of domain
concepts by design - the ingestor maps them into ``PracticalEvidence``.
"""

from pydantic import BaseModel, ConfigDict, Field


class StepResponseTelemetry(BaseModel):
    """A single step-response telemetry reading from the simulator."""

    model_config = ConfigDict(frozen=True)

    overshoot_pct: float = Field(description="Peak overshoot as a percentage.")
    settling_time_sec: float = Field(
        description="Time for the response to settle within its band, in seconds."
    )
    rise_time_sec: float = Field(description="Rise time of the step response, in seconds.")
    steady_state_error: float = Field(
        description="Residual steady-state tracking error after settling."
    )
    is_stable: bool = True


class TelemetryThresholds(BaseModel):
    """Acceptance thresholds used to pass/fail a telemetry reading."""

    model_config = ConfigDict(frozen=True)

    max_overshoot_pct: float = 10.0
    max_settling_time_sec: float = 2.0
    max_steady_state_error: float = 0.02
    require_stable: bool = True