"""Tests for the AI Coach orchestrator and anti-cheating prompt builder."""

import asyncio

import pytest
from pydantic import BaseModel

from ai_education.coach.orchestrator import (
    AICoachOrchestrator,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.coach.prompts import (
    ANTI_CHEATING_PRINCIPLES,
    build_system_prompt,
)
from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider


def run(coro) -> object:
    """Run an async coroutine to completion (no pytest-asyncio needed)."""
    return asyncio.run(coro)


def make_orchestrator(
    manager: StudentModelManager, responses: list
) -> AICoachOrchestrator:
    provider = MockLLMProvider(
        LLMConfig(provider_type="mock", model_name="mock-coach"),
        responses=responses,
    )
    return AICoachOrchestrator(student_manager=manager, llm_provider=provider)


def fresh_manager(student_id: str = "coach-student") -> StudentModelManager:
    return StudentModelManager.create_new_student(student_id)


class CoachPlan(BaseModel):
    goal: str
    hint: str


class TestTurnProcessing:
    def test_process_turn_returns_structured_response(self) -> None:
        manager = fresh_manager()
        orchestrator = make_orchestrator(manager, ["Let's learn feedback first."])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(student_id="coach-student", user_message="Help me start")
            )
        )

        assert isinstance(response, CoachTurnResponse)
        assert response.coach_message == "Let's learn feedback first."
        assert response.active_mode == CoachMode.LEARN
        assert response.target_competency_id == "MEC271-FB"
        assert response.suggested_actions  # non-empty action list
        assert all(isinstance(action, str) for action in response.suggested_actions)

    def test_async_generation_interface_is_awaitable(self) -> None:
        manager = fresh_manager()
        orchestrator = make_orchestrator(manager, ["ok"])
        request = CoachTurnRequest(student_id="coach-student", user_message="hi")

        coroutine = orchestrator.process_turn(request)

        assert asyncio.iscoroutine(coroutine)
        response = run(coroutine)
        assert response.coach_message == "ok"

    def test_empty_provider_queue_falls_back_gracefully(self) -> None:
        manager = fresh_manager()
        orchestrator = make_orchestrator(manager, [])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(student_id="coach-student", user_message="hi")
            )
        )

        assert isinstance(response, CoachTurnResponse)
        assert response.coach_message
        assert "offline" in response.coach_message.lower()


class TestModeResolution:
    def test_explicit_mode_is_used(self) -> None:
        manager = fresh_manager()
        orchestrator = make_orchestrator(manager, ["Try changing the proportional gain."])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(
                    student_id="coach-student",
                    user_message="What should I change?",
                    mode=CoachMode.PRACTICE,
                )
            )
        )

        assert response.active_mode == CoachMode.PRACTICE
        assert any("simulator" in action.lower() for action in response.suggested_actions)
        assert any("gain" in action.lower() for action in response.suggested_actions)

    def test_mode_defaults_to_learn_when_unset(self) -> None:
        manager = fresh_manager()
        orchestrator = make_orchestrator(manager, ["hi"])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(student_id="coach-student", user_message="start")
            )
        )

        assert response.active_mode == CoachMode.LEARN

    def test_refect_mode_inferred_when_all_demonstrated(self) -> None:
        manager = fresh_manager()
        for node_id in ["MEC271-FB", "MEC271-PID-FUND", "MEC271-PID-REASON",
                        "MEC271-PID-TUNE", "MEC271-RESP-ANALYSIS"]:
            manager.profile.competencies[node_id].state = CompetencyState.DEMONSTRATED
        orchestrator = make_orchestrator(manager, ["Nice work. Reflect on what you learned."])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(student_id="coach-student", user_message="I finished!")
            )
        )

        assert response.active_mode == CoachMode.REFLECT
        assert response.target_competency_id is None


class TestAntiCheatingGuardrails:
    def test_system_prompt_contains_guardrail_directives(self) -> None:
        manager = fresh_manager()
        target_node = manager.graph.get_node("MEC271-FB")
        summary = manager.get_summary()

        prompt = build_system_prompt(CoachMode.PRACTICE, target_node, summary)

        assert "Do NOT directly give PID parameter values" in prompt
        assert "overshoot if Kp increases" in prompt
        assert ANTI_CHEATING_PRINCIPLES in prompt

    def test_hint_mode_injects_guardrails_too(self) -> None:
        manager = fresh_manager()
        target_node = manager.graph.get_node("MEC271-PID-FUND")
        summary = manager.get_summary()

        prompt = build_system_prompt(CoachMode.HINT, target_node, summary)

        assert "Do NOT directly give PID parameter values" in prompt
        assert "MODE: HINT" in prompt

    def test_practice_mode_mentions_simulator_and_no_solutions(self) -> None:
        manager = fresh_manager()
        summary = manager.get_summary()
        target_node = manager.graph.get_node("MEC271-PID-TUNE")

        prompt = build_system_prompt(CoachMode.PRACTICE, target_node, summary)

        assert "pid control" in prompt.lower()  # persona present
        assert "MEC271-PID-TUNE" in prompt  # target injected
        assert "simulator" in prompt.lower()
        assert "Never reveal numeric tuning values" in prompt

    def test_prompt_includes_student_progress_context(self) -> None:
        manager = fresh_manager()
        summary = manager.get_summary()
        target_node = manager.graph.get_node("MEC271-FB")

        prompt = build_system_prompt(CoachMode.LEARN, target_node, summary)

        assert "demonstrated: 0, developing: 0, not demonstrated: 5" in prompt
        assert "MEC271-FB - Feedback Fundamentals" in prompt

    def test_prompt_handles_missing_target_node(self) -> None:
        manager = fresh_manager()
        summary = manager.get_summary()

        prompt = build_system_prompt(CoachMode.REFLECT, None, summary)

        assert "no active learning target" in prompt
        assert "Do NOT directly give PID parameter values" in prompt


class TestStructuredProviderYields:
    def test_structured_item_queued_as_object_is_usable(self) -> None:
        manager = fresh_manager()

        plan = CoachPlan(goal="Learn feedback", hint="Think about the error signal.")
        orchestrator = make_orchestrator(manager, [plan])

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(student_id="coach-student", user_message="guide me")
            )
        )

        assert isinstance(response, CoachTurnResponse)
        assert "Learn feedback" in response.coach_message
        assert "error signal" in response.coach_message

    def test_queued_dict_response_is_serialized_to_message(self) -> None:
        manager = fresh_manager()
        orchestrator = make_orchestrator(
            manager, [{"message": "Consider the overshoot trade-off."}]
        )

        response = run(
            orchestrator.process_turn(
                CoachTurnRequest(student_id="coach-student", user_message="hi")
            )
        )

        assert response.coach_message == '{"message": "Consider the overshoot trade-off."}'