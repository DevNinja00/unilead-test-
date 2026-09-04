"""REST gateway schemas for the AI/Education platform.

These models form the public HTTP contract of the gateway. They stay thin
and gateway-specific: ``MetricEvidence`` and ``PIDGains`` mirror the raw
simulator bytes a learner submits, while responses are composed from the
domain, coach, reasoning, and strategy layers that back each endpoint.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.reasoning import PIDMisconception
from ai_education.robotics.telemetry import StepResponseTelemetry
from ai_education.strategy import LearningPace, ScaffoldingLevel


class ChatRequest(BaseModel):
    """A single student chat turn submitted to the AI Coach."""

    student_id: str
    competency_id: str = Field(
        description="Target competency context, e.g. 'MEC271-PID-TUNE'."
    )
    user_message: str
    mode: Optional[CoachMode] = None


class ChatResponse(BaseModel):
    """Structured coach reply plus the active mode and scaffolding level."""

    student_id: str
    coach_message: str
    active_mode: CoachMode
    scaffolding_level: ScaffoldingLevel


class MetricEvidence(BaseModel):
    """Step-response metrics submitted from a simulator run."""

    overshoot_pct: float
    settling_time_sec: float
    rise_time_sec: float = 0.0
    steady_state_error: float
    is_stable: bool = True


class PIDGains(BaseModel):
    """PID tuning gains submitted by the learner for the run."""

    kp: float
    ki: float
    kd: float


class TelemetrySubmissionRequest(BaseModel):
    """A learner's simulator run: metrics plus the gains they chose."""

    student_id: str
    competency_id: str
    metrics: MetricEvidence
    gains: PIDGains


class TelemetrySubmissionResponse(BaseModel):
    """Outcome of ingesting one telemetry submission."""

    evidence_id: str
    diagnosed_misconception: PIDMisconception
    recommended_mode: CoachMode
    updated_competency_state: CompetencyState


class SimulateRequest(BaseModel):
    """A learner's tuning gains to run through the built-in PID simulator."""

    student_id: str
    competency_id: str
    gains: PIDGains
    setpoint: float = 1.0
    dt: float = 0.01
    duration: float = 5.0


class SimulateResponse(TelemetrySubmissionResponse):
    """Telemetry ingestion outcome plus the simulated step response."""

    telemetry: StepResponseTelemetry


class StudentProfileResponse(BaseModel):
    """A learner's full progress snapshot for a course."""

    student_id: str
    course_id: str
    total_competencies: int
    demonstrated_count: int
    developing_count: int
    not_demonstrated_count: int
    mastered_count: int
    learning_pace: LearningPace
    scaffolding_level: ScaffoldingLevel
    unblocked_ids: List[str]
    target_competency_id: Optional[str]
    completed_competency_ids: List[str]