"""TRANSFER mode: generalize PID tuning to new plants and systems."""

from typing import Any, Dict, List

from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMProvider


class TransferHandler(BaseModeHandler):
    """Maps PID tuning concepts onto a different controlled system."""

    mode = CoachMode.TRANSFER

    @staticmethod
    def transfer_scenario(context: Dict[str, Any]) -> str:
        return context.get("transfer_scenario") or (
            "temperature control for an industrial oven instead of motor speed"
        )

    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        scenario = self.transfer_scenario(context)
        extra_lines: List[str] = [
            f"Pose the same tuning principle in a new system: {scenario}.",
            "Ask how each gain (Kp, Ki, Kd) would affect the new plant, "
            "one at a time.",
            "Require the student to predict behavior before giving feedback.",
        ]
        return await self._run(request, context, llm_provider, extra_lines)