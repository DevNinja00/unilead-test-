"""Schemas for the AI Coach endpoint.

The original mock schema only accepted ``turn_index``; the wired version
accepts an optional ``mode`` (one of the six CoachMode values) and an
optional ``competency_id`` so the orchestrator can build a richer context.
The response now exposes the orchestrator's ``active_mode``,
``scaffolding_level``, and any ``suggested_actions`` produced by the mode
handler.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Mirrors ai_education.domain.enums.CoachMode — duplicated here so the
# Compass schema layer doesn't need to import the engine package.
CoachModeLiteral = Literal[
    "LEARN", "HINT", "PRACTICE", "REFLECT", "REMEDIATE", "TRANSFER"
]


class CoachRequest(BaseModel):
    """One coach turn from the student."""

    message: str = Field(..., description="The student's message to the coach.")
    mode: Optional[CoachModeLiteral] = Field(
        default=None,
        description=(
            "Optional explicit coach mode. If omitted, the reasoning engine "
            "picks one based on the student's evidence history."
        ),
    )
    competency_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional Compass competency id (e.g. 'pid-reasoning'). If "
            "omitted, the manager's current target competency is used."
        ),
    )
    student_id: str = Field(
        default="api-gateway-student",
        description="The student submitting the turn.",
    )


class CoachResponse(BaseModel):
    """The coach's reply after one turn."""

    message: str = Field(..., description="The coach's reply text.")
    active_mode: CoachModeLiteral = Field(
        ..., description="The mode that handled this turn."
    )
    target_competency_id: Optional[str] = Field(
        default=None,
        description="Compass competency id the coach is currently targeting.",
    )
    scaffolding_level: Optional[str] = Field(
        default=None,
        description="Adaptive scaffolding level (LOW / MEDIUM / HIGH).",
    )
    suggested_actions: list[str] = Field(
        default_factory=list,
        description="Suggested next actions from the mode handler.",
    )
    # Kept for backwards compatibility with the original mock UI — the
    # frontend reads ``turn_index`` and ``finished`` to manage the chat
    # flow. With the real orchestrator there's no script length, so we
    # synthesise these from the conversation size.
    turn_index: int = Field(default=0, description="Current turn index.")
    total_turns: int = Field(
        default=0,
        description=(
            "Total turns in the current scripted flow (0 means free-form, "
            "no fixed script)."
        ),
    )
    finished: bool = Field(
        default=False,
        description="True when the coach considers this competency complete.",
    )
