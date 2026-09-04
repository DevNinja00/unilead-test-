"""Evidence schemas matching the Robotics Evidence Contract.

These models define the telemetry payload that the Robotics simulation
module emits after each practical attempt, used as the canonical evidence
feed into competency tracking.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from ai_education.domain.enums import EvidenceType


class PIDParameters(BaseModel):
    """Tuned PID gains submitted by the learner for the simulation."""

    model_config = ConfigDict(frozen=True)

    kp: float
    ki: float
    kd: float


class SimulationMetrics(BaseModel):
    """Closed-loop performance metrics produced by the simulation."""

    model_config = ConfigDict(frozen=True)

    overshoot: float
    settling_time: float
    steady_state_error: float


class PracticalEvidence(BaseModel):
    """A single robotics practical attempt recorded against a task."""

    model_config = ConfigDict(frozen=True)

    evidence_type: EvidenceType = EvidenceType.PRACTICAL_SIMULATION
    task_id: str = Field(description="Task identifier, e.g. 'PID-001'.")
    attempt: int = Field(ge=1, description="1-based attempt number for the task.")
    parameters: PIDParameters
    metrics: SimulationMetrics
    stable: bool
    requirements_met: bool
    result: str = Field(description="Outcome of the attempt, e.g. 'PASS' or 'FAIL'.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of when the evidence was produced.",
    )