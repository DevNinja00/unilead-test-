"""PRACTICE mode: guided simulator tuning without handing over solutions."""

from typing import Any, Dict, List

from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMProvider


class PracticeHandler(BaseModeHandler):
    """Guides one gain change at a time and withholds numeric solutions."""

    mode = CoachMode.PRACTICE

    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        extra_lines: List[str] = [
            "Guide the student through one gain change at a time on the simulator.",
            "Make the student predict the step response before running any change.",
            "Never reveal numeric tuning values or the optimal controller gains.",
        ]
        return await self._run(request, context, llm_provider, extra_lines)