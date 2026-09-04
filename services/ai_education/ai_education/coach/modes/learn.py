"""LEARN mode: introduce concepts while keeping the student reasoning."""

from typing import Any, Dict, List

from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMProvider


class LearnHandler(BaseModeHandler):
    """Introduces new concepts with an analogy and a final check-in question."""

    mode = CoachMode.LEARN

    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        extra_lines: List[str] = [
            "Anchor the concept in an intuitive analogy before introducing formulas.",
            "Keep the explanation at the current competency's level without "
            "pre-solving tuning tasks.",
            "End the reply with one conceptual check-in question for the "
            "student to answer.",
        ]
        target_node = context.get("target_node")
        if target_node is not None:
            extra_lines.append(
                f"Frame the explanation around the target competency "
                f"{target_node.id}."
            )
        return await self._run(request, context, llm_provider, extra_lines)