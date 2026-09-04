"""AI Coach orchestrator: wires the student model, LLM provider, and handlers.

Each ``process_turn`` call resolves a ``CoachMode``, delegates the turn to a
dedicated per-mode handler from the registry, and returns the structured
``CoachTurnResponse`` the handler produced. Handlers assemble the guarded
system context (with anti-cheating guardrails) themselves; the orchestrator
only routes the request. The provider layer is injected, so the same
orchestrator runs against Ollama, OpenAI, or the offline Mock provider.
"""

from typing import Dict, List, Optional

from ai_education.coach.modes import build_handler_registry
from ai_education.coach.modes.base import (
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.enums import CoachMode
from ai_education.domain.models import CompetencyNode, CompetencyRecord
from ai_education.domain.student import StudentModelManager
from ai_education.fallbacks.engine import FallbackEngine
from ai_education.llm.base import LLMProvider
from ai_education.reasoning import PIDMisconception, diagnose_misconception
from ai_education.robotics import StepResponseTelemetry
from ai_education.strategy import (
    LearningPace,
    ScaffoldingLevel,
    evaluate_pace,
    evaluate_scaffolding_level,
)

__all__ = ["AICoachOrchestrator", "CoachTurnRequest", "CoachTurnResponse"]


class AICoachOrchestrator:
    """Runs one coach turn, routed through a per-mode handler registry."""

    def __init__(
        self,
        student_manager: StudentModelManager,
        llm_provider: LLMProvider,
        fallback_engine: Optional[FallbackEngine] = None,
    ) -> None:
        self.student_manager: StudentModelManager = student_manager
        self.llm_provider: LLMProvider = llm_provider
        self.fallback_engine: FallbackEngine = fallback_engine or FallbackEngine()
        self.mode_handlers: Dict[CoachMode, BaseModeHandler] = (
            build_handler_registry()
        )

    def _resolve_mode(
        self, request: CoachTurnRequest, target_node: Optional[CompetencyNode]
    ) -> CoachMode:
        """Use the requested mode, or infer one from the learner's state."""
        if request.mode is not None:
            return request.mode
        summary = self.student_manager.get_summary()
        demonstrated = int(summary["demonstrated_count"])
        total = int(summary["total_competencies"])
        if demonstrated >= total:
            return CoachMode.REFLECT
        return CoachMode.LEARN

    def _get_handler(self, mode: CoachMode) -> BaseModeHandler:
        try:
            return self.mode_handlers[mode]
        except KeyError as exc:
            raise ValueError(f"No mode handler registered for {mode!r}") from exc

    def _build_context(
        self,
        target_node: Optional[CompetencyNode],
        summary: Dict[str, object],
        record: Optional[CompetencyRecord],
    ) -> Dict[str, object]:
        """Assemble the context dictionary handed to the mode handler."""
        context: Dict[str, object] = {
            "target_node": target_node,
            "summary": summary,
        }
        if record is not None:
            context["record"] = record
        return context

    def _remediate_record(
        self, request: CoachTurnRequest, target_node: Optional[CompetencyNode]
    ) -> Optional[CompetencyRecord]:
        """A failing competency's record for REMEDIATE turns, when available."""
        if request.mode is not CoachMode.REMEDIATE or target_node is None:
            return None
        return self.student_manager.profile.competencies.get(target_node.id)

    async def process_turn(self, request: CoachTurnRequest) -> CoachTurnResponse:
        """Resolve the mode and delegate the turn to its dedicated handler."""
        target_node = self.student_manager.get_next_target_competency()
        summary = self.student_manager.get_summary()
        active_mode = self._resolve_mode(request, target_node)
        record = self._remediate_record(request, target_node)
        context = self._build_context(target_node, summary, record)
        handler = self._get_handler(active_mode)
        try:
            return await handler.handle_turn(request, context, self.llm_provider)
        except Exception:
            # Demo hardening: a failed LLM call must never surface as a 500.
            # Fall back to deterministic, mode-appropriate pedagogy.
            return self._build_fallback_turn(
                request, active_mode, target_node, record
            )

    @staticmethod
    def _trailing_failures(record: CompetencyRecord) -> int:
        """Count trailing attempts that did not meet requirements."""
        count = 0
        for evidence in reversed(record.evidence_history):
            if evidence.requirements_met:
                break
            count += 1
        return count

    def _learning_pace(self) -> LearningPace:
        """Derive the current pace straight from recorded evidence."""
        records = list(self.student_manager.profile.competencies.values())
        total_attempts = sum(
            len(record.evidence_history) for record in records
        )
        total_failures = sum(
            1
            for record in records
            for evidence in record.evidence_history
            if not evidence.requirements_met
        )
        competencies_attempted = sum(
            1 for record in records if record.evidence_history
        )
        consecutive_failures = max(
            (self._trailing_failures(record) for record in records),
            default=0,
        )
        return evaluate_pace(
            total_attempts=total_attempts,
            total_failures=total_failures,
            competencies_attempted=competencies_attempted,
            consecutive_failures=consecutive_failures,
        )

    def _misconception_for(
        self, record: Optional[CompetencyRecord]
    ) -> PIDMisconception:
        """Diagnose the learner's latest misconception, when available."""
        if record is None or not record.evidence_history:
            return PIDMisconception.NONE
        latest = record.evidence_history[-1]
        return diagnose_misconception(
            StepResponseTelemetry(
                overshoot_pct=latest.metrics.overshoot,
                settling_time_sec=latest.metrics.settling_time,
                rise_time_sec=0.0,
                steady_state_error=latest.metrics.steady_state_error,
                is_stable=latest.stable,
            )
        )

    def _build_fallback_turn(
        self,
        request: CoachTurnRequest,
        active_mode: CoachMode,
        target_node: Optional[CompetencyNode],
        record: Optional[CompetencyRecord],
    ) -> CoachTurnResponse:
        """Serve deterministic pedagogy when the LLM provider is offline."""
        competency_id = target_node.id if target_node else None
        scaffolding = evaluate_scaffolding_level(self._learning_pace())
        fallback = self.fallback_engine.generate_fallback_response(
            student_id=request.student_id,
            competency_id=competency_id,
            mode=active_mode,
            misconception=self._misconception_for(record),
            scaffolding=scaffolding,
        )
        return CoachTurnResponse(
            coach_message=fallback.coach_message,
            active_mode=active_mode,
            target_competency_id=competency_id,
            suggested_actions=fallback.suggested_actions,
        )