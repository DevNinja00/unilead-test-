"""Schemas for the Remediation endpoint.

Remediation is offered when a student has ≥2 consecutive failing simulation
attempts on a competency. The ``RemediationEngine`` analyses the failure
telemetry, picks an action (EXPLAIN_CONCEPT / ADJUST_PARAMETER_STEP /
REVIEW_PREREQUISITE / RESET_EXPERIMENT), and returns a micro-lesson with
guided questions + steps.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RemediationPlanResponse(BaseModel):
    """A targeted remediation plan for one competency."""

    competency_id: str = Field(..., description="Compass competency id.")
    detected_misconception: Optional[str] = Field(
        default=None,
        description="PID misconception detected from the failure telemetry.",
    )
    recommended_action: str = Field(
        ..., description="Remediation action type (see RemediationAction enum)."
    )
    conceptual_focus: str = Field(
        ..., description="The concept the remediation should focus on."
    )
    guided_question: str = Field(
        ..., description="One open question the student should answer next."
    )
    remediation_steps: list[str] = Field(
        default_factory=list,
        description="Ordered micro-lesson steps the student should follow.",
    )
    consecutive_failures: int = Field(
        default=0, description="How many recent attempts have failed in a row."
    )
    total_attempts: int = Field(
        default=0, description="Total simulation attempts on this competency."
    )
    summary_text: str = Field(
        default="", description="Human-readable summary of the reasoning."
    )
