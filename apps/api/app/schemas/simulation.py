"""Schemas for the PID simulation endpoint.

The original mock schema only accepted ``task_id``; this wired version
accepts ``kp``, ``ki``, ``kd`` plus an optional ``competency_id`` and
returns the full evidence record (metrics + requirements_met + result +
attempt number).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    """Run a PID simulation with the given gains."""

    kp: float = Field(default=2.0, ge=-100.0, le=100.0, description="Proportional gain.")
    ki: float = Field(default=0.5, ge=-100.0, le=100.0, description="Integral gain.")
    kd: float = Field(default=0.1, ge=-100.0, le=100.0, description="Derivative gain.")
    competency_id: str | None = Field(
        default="pid-tuning",
        max_length=64,
        description="Compass competency id this simulation is evidence for.",
    )
    task_id: str = Field(
        default="pid-001",
        max_length=64,
        description="Identifier of the task the student is solving.",
    )


class SimulationResult(BaseModel):
    """Outcome of one PID simulation run."""

    stable: bool
    overshoot: float
    settling_time: float
    rise_time: float
    steady_state_error: float

    # New evidence-oriented fields (wired version)
    kp: float = Field(..., description="The Kp used in this run.")
    ki: float = Field(..., description="The Ki used in this run.")
    kd: float = Field(..., description="The Kd used in this run.")
    requirements_met: bool = Field(..., description="True if all task thresholds were met.")
    result: str = Field(..., description="'PASS' or 'FAIL'.")
    attempt: int = Field(..., description="1-based attempt number for this competency.")
    competency_id: str = Field(..., description="Compass competency id this run is evidence for.")
    misconception: str | None = Field(
        default=None,
        description="Detected PID misconception (only set on FAIL).",
    )
