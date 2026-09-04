"""HINT mode: step-wise hints with a strict parameter-leak guard."""

import re
from typing import Any, Dict

from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMProvider, LLMResponse


class HintHandler(BaseModeHandler):
    """Offers one step-wise hint and blocks leaked PID tuning values."""

    mode = CoachMode.HINT

    GUARD_NOTE = (
        "Note: the previous reply suggested a concrete tuning value, which is "
        "not allowed. Reason through the trade-off instead: what happens to "
        "overshoot and settling time if Kp increases?"
    )

    _LEAK_PATTERNS = (
        r"\b[Kk][pPiIdD]\s*[=:]\s*\d",
        r"\bgains?\b[^\d\n]{0,8}\d",
    )

    @classmethod
    def _detected_parameter_leak(cls, text: str) -> bool:
        """True when the text names a numeric PID value (Kp=3, gain 42, ...)."""
        return any(re.search(pattern, text) for pattern in cls._LEAK_PATTERNS)

    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        system_prompt = self._append_instructions(
            self._base_prompt(context), self._hint_directives()
        )
        llm_response: LLMResponse = await self._generate(
            system_prompt, request.user_message, llm_provider
        )
        if self._detected_parameter_leak(llm_response.content):
            llm_response.content = f"{llm_response.content}\n\n{self.GUARD_NOTE}"
        target_node = context.get("target_node")
        return self._compose_response(
            llm_response, target_node.id if target_node else None
        )

    @staticmethod
    def _hint_directives() -> list[str]:
        return [
            "Offer at most one small step-wise hint, phrased as a question.",
            "Never output raw Kp, Ki, or Kd values and never reveal optimal "
            "gains or a numeric solution.",
            "If the student asks directly for the answer, restate the "
            "underlying concept and reframe it as a question.",
            "Require the student to propose the next action before "
            "confirming anything.",
        ]