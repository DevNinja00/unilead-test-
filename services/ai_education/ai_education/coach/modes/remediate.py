"""REMEDIATE mode: inject metric failures and rebuild foundations."""

from typing import Any, Dict, List

from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.llm.base import LLMProvider


class RemediateHandler(BaseModeHandler):
    """Addresses demonstrated weaknesses with concrete metric failures."""

    mode = CoachMode.REMEDIATE

    @staticmethod
    def metric_failures(context: Dict[str, Any]) -> List[str]:
        """Return failure lines from failing evidence, or a default."""
        record = context.get("record")
        failures: List[str] = []
        evidence_history = getattr(record, "evidence_history", None)
        if evidence_history is not None:
            for evidence in evidence_history:
                if evidence.requirements_met:
                    continue
                metrics = evidence.metrics
                if metrics.overshoot > 20.0:
                    failures.append(
                        f"step-response overshoot was {metrics.overshoot:.1f}% "
                        f"(target <= 20%)"
                    )
                if metrics.settling_time > 1.5:
                    failures.append(
                        f"settling time was {metrics.settling_time:.2f}s "
                        f"(target <= 1.5s)"
                    )
                if metrics.steady_state_error > 0.05:
                    failures.append(
                        f"steady-state error was {metrics.steady_state_error:.3f} "
                        f"(target <= 0.05)"
                    )
        if not failures:
            failures.append("step-response overshoot exceeded 20%")
        return failures

    async def handle_turn(
        self,
        request: CoachTurnRequest,
        context: Dict[str, Any],
        llm_provider: LLMProvider,
    ) -> CoachTurnResponse:
        extra_lines: List[str] = self.metric_failures(context)
        extra_lines.extend(
            [
                "Diagnose the misconception behind the failing metric before "
                "proposing a retry.",
                "Rebuild the foundational concept with one quick exercise.",
                "Do not hand over the correct settings for the simulator.",
            ]
        )
        return await self._run(request, context, llm_provider, extra_lines)