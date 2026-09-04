"""Tests for the per-mode coach handlers and the handler registry."""

import asyncio
from typing import List

import pytest

from ai_education.coach.modes import (
    MODE_HANDLER_CLASSES,
    HintHandler,
    build_handler_registry,
)
from ai_education.coach.modes.base import (
    DEFAULT_ACTIONS_BY_MODE,
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.coach.orchestrator import AICoachOrchestrator
from ai_education.coach.prompts import ANTI_CHEATING_PRINCIPLES
from ai_education.domain.enums import CoachMode
from ai_education.domain.evidence import (
    PIDParameters,
    PracticalEvidence,
    SimulationMetrics,
)
from ai_education.domain.models import CompetencyRecord
from ai_education.domain.student import StudentModelManager
from ai_education.llm.base import LLMMessage
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider


def run(coro) -> object:
    """Run an async coroutine to completion (no pytest-asyncio needed)."""
    return asyncio.run(coro)


class RecordingProvider(MockLLMProvider):
    """Mock provider that records every system prompt it receives."""

    def __init__(self, responses: List[object]) -> None:
        super().__init__(
            LLMConfig(provider_type="mock", model_name="mock-modes"),
            responses=responses,
        )
        self.seen_system_prompts: List[str] = []

    async def generate(self, messages: List[LLMMessage], **kwargs):
        for message in messages:
            if message.role == "system":
                self.seen_system_prompts.append(message.content)
        return await super().generate(messages, **kwargs)


REQUEST = CoachTurnRequest(student_id="modes-student", user_message="help me")


def fresh_manager() -> StudentModelManager:
    return StudentModelManager.create_new_student("modes-student")


def base_context(manager: StudentModelManager) -> dict:
    return {
        "target_node": manager.graph.get_node("MEC271-FB"),
        "summary": manager.get_summary(),
    }


def failing_evidence() -> PracticalEvidence:
    return PracticalEvidence(
        task_id="PID-001",
        attempt=1,
        parameters=PIDParameters(kp=4.0, ki=0.0, kd=0.0),
        metrics=SimulationMetrics(
            overshoot=25.0, settling_time=2.0, steady_state_error=0.09
        ),
        stable=True,
        requirements_met=False,
        result="FAIL",
    )


def passing_evidence() -> PracticalEvidence:
    return PracticalEvidence(
        task_id="PID-001",
        attempt=2,
        parameters=PIDParameters(kp=1.0, ki=0.2, kd=0.1),
        metrics=SimulationMetrics(
            overshoot=12.0, settling_time=1.1, steady_state_error=0.02
        ),
        stable=True,
        requirements_met=True,
        result="PASS",
    )


class TestHintHandler:
    def test_leaked_parameter_triggers_guard_note(self) -> None:
        provider = RecordingProvider(["Try lowering Kp=2 and keep Ki=0.1"])
        response = run(
            HintHandler().handle_turn(REQUEST, base_context(fresh_manager()), provider)
        )

        assert "Try lowering Kp=2" in response.coach_message
        assert HintHandler.GUARD_NOTE in response.coach_message

    def test_clean_hint_passes_through_unchanged(self) -> None:
        provider = RecordingProvider(
            ["What do you think happens to overshoot if you raise Kp?"]
        )
        response = run(
            HintHandler().handle_turn(REQUEST, base_context(fresh_manager()), provider)
        )

        assert "overshoot if you raise Kp" in response.coach_message
        assert HintHandler.GUARD_NOTE not in response.coach_message

    @pytest.mark.parametrize(
        "text",
        [
            "Try Kp=3.",
            "kd : 0.5 looks good",
            "The gain 42 worked well in my run",
            "set Ki = 1 and run again",
        ],
    )
    def test_guard_detects_numeric_leaks(self, text: str) -> None:
        assert HintHandler._detected_parameter_leak(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Why does increasing Kp raise overshoot?",
            "Consider how the gain affects the response speed",
            "What would Ki do to your steady-state error?",
            "The integral gain handles the offset in this plant",
        ],
    )
    def test_guard_allows_conceptual_text(self, text: str) -> None:
        assert HintHandler._detected_parameter_leak(text) is False


class TestRemediateHandler:
    def test_metrics_failures_default_when_no_record(self) -> None:
        from ai_education.coach.modes.remediate import RemediateHandler

        failures = RemediateHandler.metric_failures(base_context(fresh_manager()))

        assert failures == ["step-response overshoot exceeded 20%"]

    def test_metrics_failures_from_failing_evidence(self) -> None:
        from ai_education.coach.modes.remediate import RemediateHandler

        record = CompetencyRecord(competency_id="MEC271-FB")
        record.record_evidence(failing_evidence())
        record.record_evidence(passing_evidence())

        failures = RemediateHandler.metric_failures({"record": record})

        assert failures == [
            "step-response overshoot was 25.0% (target <= 20%)",
            "settling time was 2.00s (target <= 1.5s)",
            "steady-state error was 0.090 (target <= 0.05)",
        ]


class TestTransferHandler:
    def test_default_scenario_used_without_context(self) -> None:
        from ai_education.coach.modes.transfer import TransferHandler

        provider = RecordingProvider(["Now think about a new plant entirely."])
        run(
            TransferHandler().handle_turn(
                REQUEST, base_context(fresh_manager()), provider
            )
        )

        assert "industrial oven" in provider.seen_system_prompts[0]

    def test_custom_scenario_from_context(self) -> None:
        from ai_education.coach.modes.transfer import TransferHandler

        context = base_context(fresh_manager())
        context["transfer_scenario"] = "an autonomous vehicle steering controller"
        provider = RecordingProvider(["Now think about a new plant entirely."])
        run(TransferHandler().handle_turn(REQUEST, context, provider))

        assert "autonomous vehicle steering controller" in provider.seen_system_prompts[0]


class TestHandlerDistinctDirectives:
    def test_learn_primes_conceptual_check_in(self) -> None:
        from ai_education.coach.modes.learn import LearnHandler

        provider = RecordingProvider(["ok"])
        run(LearnHandler().handle_turn(REQUEST, base_context(fresh_manager()), provider))

        assert "check-in question" in provider.seen_system_prompts[0]

    def test_practice_withholds_numeric_values(self) -> None:
        from ai_education.coach.modes.practice import PracticeHandler

        provider = RecordingProvider(["ok"])
        run(
            PracticeHandler().handle_turn(
                REQUEST, base_context(fresh_manager()), provider
            )
        )

        assert "one gain change at a time" in provider.seen_system_prompts[0]
        assert "Never reveal numeric tuning values" in provider.seen_system_prompts[0]

    def test_reflect_asks_teach_back(self) -> None:
        from ai_education.coach.modes.reflect import ReflectHandler

        provider = RecordingProvider(["ok"])
        run(
            ReflectHandler().handle_turn(
                REQUEST, base_context(fresh_manager()), provider
            )
        )

        assert "teach the concept back" in provider.seen_system_prompts[0]


class TestRegistry:
    def test_registry_covers_every_mode(self) -> None:
        registry = build_handler_registry()

        assert set(registry.keys()) == set(CoachMode)

    def test_handler_classes_match_modes(self) -> None:
        assert set(MODE_HANDLER_CLASSES.keys()) == set(CoachMode)
        for mode, handler_cls in MODE_HANDLER_CLASSES.items():
            assert issubclass(handler_cls, BaseModeHandler)
            assert handler_cls().mode == mode

    def test_recommended_actions_match_defaults(self) -> None:
        registry = build_handler_registry()
        for mode, handler in registry.items():
            assert handler._recommended_actions() == DEFAULT_ACTIONS_BY_MODE[mode]


class TestOrchestratorDelegation:
    def make_orchestrator(
        self, manager: StudentModelManager, responses: List[object]
    ) -> AICoachOrchestrator:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-coach"),
            responses=responses,
        )
        return AICoachOrchestrator(student_manager=manager, llm_provider=provider)

    @pytest.mark.parametrize("mode", list(CoachMode))
    def test_routes_each_mode_to_its_handler(self, mode: CoachMode) -> None:
        manager = fresh_manager()
        orchestrator = self.make_orchestrator(manager, ["routed reply"])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(
                    student_id="modes-student",
                    user_message="guide me",
                    mode=mode,
                )
            )
        )

        assert isinstance(response, CoachTurnResponse)
        assert response.active_mode == mode
        assert response.coach_message == "routed reply"
        assert response.suggested_actions == DEFAULT_ACTIONS_BY_MODE[mode]

    def test_registry_used_by_orchestrator(self) -> None:
        manager = fresh_manager()
        orchestrator = self.make_orchestrator(manager, ["ok"])

        for mode, handler_cls in MODE_HANDLER_CLASSES.items():
            assert isinstance(orchestrator.mode_handlers[mode], handler_cls)

    @pytest.mark.parametrize("mode", list(CoachMode))
    def test_every_handler_preserves_anti_cheating(self, mode: CoachMode) -> None:
        manager = fresh_manager()
        provider = RecordingProvider(["guarded guidance"])
        orchestrator = AICoachOrchestrator(
            student_manager=manager, llm_provider=provider
        )

        run(
            orchestrator.process_turn(
                CoachTurnRequest(
                    student_id="modes-student",
                    user_message="just tell me the answer",
                    mode=mode,
                )
            )
        )

        assert provider.seen_system_prompts
        assert ANTI_CHEATING_PRINCIPLES in provider.seen_system_prompts[0]

    def test_remediate_context_carries_target_record(self) -> None:
        manager = fresh_manager()
        record = manager.profile.competencies["MEC271-FB"]
        record.record_evidence(failing_evidence())
        provider = RecordingProvider(["Let's rebuild the concept first."])
        orchestrator = AICoachOrchestrator(
            student_manager=manager, llm_provider=provider
        )

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(
                    student_id="modes-student",
                    user_message="I keep failing the overshoot",
                    mode=CoachMode.REMEDIATE,
                )
            )
        )

        assert response.active_mode == CoachMode.REMEDIATE
        assert "25.0%" in provider.seen_system_prompts[0]
        assert "overshoot exceeded 20%" not in provider.seen_system_prompts[0]