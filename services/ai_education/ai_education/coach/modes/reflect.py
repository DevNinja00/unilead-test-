"""REFLECT mode: teach-back and conceptual self-assessment."""

from typing import Any, Dict, List

from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMProvider


class ReflectHandler(BaseModeHandler):
    """Asks teach-back questions that require conceptual explanation."""

    mode = CoachMode.REFLECT

    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        extra_lines: List[str] = [
            "Ask the student to teach the concept back in their own words.",
            "Pose one question that requires a conceptual explanation, not recognition.",
            "Prompt the student to identify what surprised them and connect "
            "it to the next competency.",
        ]
        return await self._run(request, context, llm_provider, extra_lines)