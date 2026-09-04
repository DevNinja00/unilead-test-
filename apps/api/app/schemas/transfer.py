"""Schemas for the Transfer endpoint.

A Transfer task presents the student with a new plant scenario (e.g.
industrial oven, water tank, quadrotor pitch) and asks them to apply
their PID reasoning in that new domain. The student submits a free-text
response; the ``TransferAssessmentEngine`` evaluates it deterministically
(no LLM) by matching against expert domain terms.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TransferScenarioResponse(BaseModel):
    """A transfer challenge presented to the student."""

    competency_id: str = Field(..., description="Compass competency id being transferred.")
    scenario_id: str = Field(..., description="Identifier of the transfer scenario.")
    title: str = Field(..., description="Human-readable scenario title.")
    domain: str = Field(..., description="Domain label (e.g. 'thermal', 'fluid', 'aerospace').")
    prompt: str = Field(..., description="The challenge prompt shown to the student.")
    error_signal_meaning: str = Field(
        ..., description="What the error signal represents in this domain."
    )
    control_output_meaning: str = Field(..., description="What the control output represents.")
    system_inertia: str = Field(..., description="Qualitative description of system inertia.")
    conceptual_challenge: str = Field(
        ..., description="The reasoning challenge the student must address."
    )
    # No solution steps are provided — by design.


class TransferEvaluationRequest(BaseModel):
    """Student's response to a transfer prompt."""

    response_text: str = Field(
        ..., description="The student's free-text response to the transfer prompt."
    )
    scenario_id: str = Field(
        default="industrial_oven", description="Which scenario is being answered."
    )


class TransferEvaluationResponse(BaseModel):
    """Outcome of a transfer evaluation."""

    competency_id: str
    scenario_id: str
    passed: bool = Field(..., description="True if the response matched enough expert terms.")
    matched_terms: list[str] = Field(
        default_factory=list, description="Expert terms detected in the response."
    )
    matched_count: int
    min_required: int
    feedback: str = Field(..., description="Coaching feedback based on the result.")
