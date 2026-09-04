"""Shared DTOs, fallback actions, and the abstract mode-handler interface.

The modes package owns the turn request/response models so the dependency
flow stays one-way: orchestrator -> modes -> (domain, prompts, llm). The
helpers here keep every handler's shell identical, so mode logic is the
only thing that differs between handlers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ai_education.coach.prompts import build_system_prompt
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMMessage, LLMProvider, LLMResponse

DEFAULT_ACTIONS_BY_MODE: Dict[CoachMode, List[str]] = {
    CoachMode.LEARN: [
        "Review the concept at the target competency's level",
        "Ask a conceptual check-in question",
    ],
    CoachMode.HINT: [
        "Offer a single small hint phrased as a question",
        "Let the student propose the next gain change",
    ],
    CoachMode.PRACTICE: [
        "Run a tuning attempt in the simulator",
        "Explain your reasoning for each gain change before running",
        "Predict the step response before you apply the change",
    ],
    CoachMode.REFLECT: [
        "Summarize what you learned this session",
        "Identify one thing that surprised you",
    ],
    CoachMode.REMEDIATE: [
        "Diagnose the misconception behind the last failure",
        "Rebuild the foundational concept with quick exercises",
    ],
    CoachMode.TRANSFER: [
        "Generalize the learned principle to a new scenario",
        "Explain how the concept would behave in a different plant",
    ],
}


class CoachTurnRequest(BaseModel):
    """A single turn from the student chat."""

    student_id: str
    user_message: str
    mode: Optional[CoachMode] = None


class CoachTurnResponse(BaseModel):
    """A structured reply from the AI Coach."""

    coach_message: str
    active_mode: CoachMode
    target_competency_id: Optional[str] = None
    suggested_actions: List[str] = Field(default_factory=list)


class BaseModeHandler(ABC):
    """Template that the specialized per-mode handlers implement."""

    mode: CoachMode

    @staticmethod
    def _append_instructions(system_prompt: str, extra_lines: List[str]) -> str:
        """Append mode-specific directive lines to a system prompt."""
        if not extra_lines:
            return system_prompt
        block = "\n".join(f"- {line}" for line in extra_lines)
        return f"{system_prompt}\n{block}\n"

    def _base_prompt(self, context: Dict[str, Any]) -> str:
        """The guarded base system prompt for this handler's mode."""
        return build_system_prompt(
            self.mode,
            context.get("target_node"),
            context.get("summary") or {},
        )

    def _recommended_actions(self) -> List[str]:
        """Deterministic fallback suggested actions for this mode."""
        return list(DEFAULT_ACTIONS_BY_MODE[self.mode])

    @staticmethod
    def _messages(system_prompt: str, user_message: str) -> List[LLMMessage]:
        return [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_message),
        ]

    async def _generate(
        self,
        system_prompt: str,
        user_message: str,
        llm_provider: LLMProvider,
    ) -> LLMResponse:
        """Call the provider with this handler's system/user messages."""
        return await llm_provider.generate(
            self._messages(system_prompt, user_message)
        )

    def _compose_response(
        self, llm_response: LLMResponse, target_competency_id: Optional[str]
    ) -> CoachTurnResponse:
        return CoachTurnResponse(
            coach_message=llm_response.content,
            active_mode=self.mode,
            target_competency_id=target_competency_id,
            suggested_actions=self._recommended_actions(),
        )

    async def _run(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
        extra_lines: List[str],
    ) -> CoachTurnResponse:
        """Standard turn shell: prompt + directives -> provider -> response."""
        system_prompt = self._append_instructions(
            self._base_prompt(context), extra_lines
        )
        llm_response = await self._generate(
            system_prompt, request.user_message, llm_provider
        )
        target_node = context.get("target_node")
        return self._compose_response(
            llm_response, target_node.id if target_node else None
        )

    @abstractmethod
    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        """Produce a structured coach reply for one mode-specific turn."""