"""Demo hardening and offline fallback tests.

Verifies three guarantees: (1) ``FallbackEngine`` produces valid, mode-aware
pedagogical replies without an LLM, (2) the orchestrator degrades gracefully
instead of raising HTTP 500 when the provider raises, and (3) the demo
fixtures load and are structurally valid.
"""

import asyncio
from typing import Any, List

import pytest
from fastapi.testclient import TestClient

from ai_education.api.app import create_app
from ai_education.api.schemas import MetricEvidence, PIDGains
from ai_education.coach.modes.base import CoachTurnRequest, CoachTurnResponse
from ai_education.coach.orchestrator import AICoachOrchestrator
from ai_education.domain.courses.mec271 import MEC271_NODE_IDS
from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.domain.evidence import (
    PIDParameters,
    PracticalEvidence,
    SimulationMetrics,
)
from ai_education.domain.student import StudentModelManager
from ai_education.fallbacks import (
    CoachResponse,
    FallbackEngine,
    get_demo_student_profiles,
    get_demo_telemetry_samples,
)
from ai_education.llm.base import LLMMessage, LLMProvider, LLMProviderError
from ai_education.llm.config import LLMConfig
from ai_education.reasoning import PIDMisconception, diagnose_misconception
from ai_education.robotics import StepResponseTelemetry
from ai_education.strategy import LearningPace, ScaffoldingLevel

ENGINE = FallbackEngine()

STUDENT_ID = "demo-fallback-student"
COMPETENCY_ID = "MEC271-FB"


class RaisingLLMProvider(LLMProvider):
    """A provider that always fails, simulating a full LLM outage."""

    def __init__(self, exception_cls: Any = RuntimeError) -> None:
        super().__init__(LLMConfig(provider_type="mock", model_name="broken"))
        self._exception_cls: Any = exception_cls

    @classmethod
    def _expected_provider_type(cls) -> str:
        return "mock"

    async def generate(
        self, messages: List[LLMMessage], **kwargs: Any
    ) -> Any:
        raise self._exception_cls("simulated LLM provider outage")

    async def generate_structured(
        self, messages: List[LLMMessage], response_schema: Any
    ) -> Any:
        raise self._exception_cls("simulated LLM provider outage")


class TestFallbackResponseGeneration:
    @pytest.mark.parametrize("mode", list(CoachMode))
    def test_fallback_response_for_all_coach_modes(self, mode: CoachMode) -> None:
        # DIAGNOSE has no CoachMode member (diagnosis is handled by the
        # offline EvidenceReasoningEngine), so every real mode is covered.
        response = ENGINE.generate_fallback_response(
            student_id=STUDENT_ID,
            competency_id=COMPETENCY_ID,
            mode=mode,
            misconception=PIDMisconception.UNSTABLE_TUNING,
            scaffolding=ScaffoldingLevel.HIGH,
        )
        assert isinstance(response, CoachResponse)
        assert response.from_fallback is True
        assert response.active_mode is mode
        assert response.student_id == STUDENT_ID
        assert response.misconception is PIDMisconception.UNSTABLE_TUNING
        assert response.scaffolding_level is ScaffoldingLevel.HIGH
        assert response.coach_message
        assert "offline" in response.coach_message.lower()
        assert response.suggested_actions

    def test_fallback_remediate_embeds_misconception_guidance(self) -> None:
        response = ENGINE.generate_fallback_response(
            student_id=STUDENT_ID,
            competency_id=COMPETENCY_ID,
            mode=CoachMode.REMEDIATE,
            misconception=PIDMisconception.UNSTABLE_TUNING,
            scaffolding=ScaffoldingLevel.HIGH,
        )
        assert "unstable" in response.coach_message.lower()
        assert "offline" in response.coach_message.lower()


class TestOrchestratorGracefulRecovery:
    @pytest.mark.parametrize(
        "error_cls", [RuntimeError, LLMProviderError]
    )
    def test_orchestrator_fallback_recovery(self, error_cls: Any) -> None:
        manager = StudentModelManager.create_new_student(STUDENT_ID)
        manager.record_evidence(
            "MEC271-FB",
            PracticalEvidence(
                task_id="MEC271-FB",
                attempt=1,
                parameters=PIDParameters(kp=25.0, ki=0.0, kd=0.0),
                metrics=SimulationMetrics(
                    overshoot=30.0,
                    settling_time=3.5,
                    steady_state_error=0.10,
                ),
                stable=False,
                requirements_met=False,
                result="FAIL",
            ),
        )
        orchestrator = AICoachOrchestrator(
            student_manager=manager,
            llm_provider=RaisingLLMProvider(error_cls),
        )

        acts = asyncio.run(
            orchestrator.process_turn(
                CoachTurnRequest(
                    student_id=STUDENT_ID,
                    user_message="The plant went unstable.",
                    mode=CoachMode.REMEDIATE,
                )
            )
        )
        assert isinstance(acts, CoachTurnResponse)
        assert acts.active_mode is CoachMode.REMEDIATE
        assert acts.target_competency_id == "MEC271-FB"
        assert acts.suggested_actions
        assert "offline" in acts.coach_message.lower()
        assert "unstable" in acts.coach_message.lower()

    def test_fallback_learn_mode_recovers_without_evidence(self) -> None:
        manager = StudentModelManager.create_new_student(STUDENT_ID)
        orchestrator = AICoachOrchestrator(
            student_manager=manager,
            llm_provider=RaisingLLMProvider(RuntimeError),
        )
        reply = asyncio.run(
            orchestrator.process_turn(
                CoachTurnRequest(
                    student_id=STUDENT_ID,
                    user_message="Where do we start?",
                    mode=CoachMode.LEARN,
                )
            )
        )
        assert isinstance(reply, CoachTurnResponse)
        assert reply.active_mode is CoachMode.LEARN
        assert reply.target_competency_id == "MEC271-FB"
        assert "offline" in reply.coach_message.lower()
        assert "MEC271-FB" in reply.coach_message

    def test_gateway_chat_returns_200_when_provider_fails(self) -> None:
        manager = StudentModelManager.create_new_student(STUDENT_ID)
        app = create_app(
            student_manager=manager,
            llm_provider=RaisingLLMProvider(RuntimeError),
        )
        with TestClient(app) as client:
            response = client.post(
                "/coach/chat",
                json={
                    "student_id": STUDENT_ID,
                    "competency_id": COMPETENCY_ID,
                    "user_message": "Help me understand PID.",
                    "mode": CoachMode.LEARN.value,
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["active_mode"] == CoachMode.LEARN.value
        assert "offline" in body["coach_message"].lower()
        assert body["scaffolding_level"]


class TestDemoFixtures:
    def test_demo_student_profiles_load_and_validate(self) -> None:
        profiles = get_demo_student_profiles()
        assert set(profiles) == {
            "Struggling Sam",
            "Progressing Pat",
            "Mastering Morgan",
        }
        pace_values = {pace.value for pace in LearningPace}
        scaffold_values = {level.value for level in ScaffoldingLevel}
        state_values = {state.value for state in CompetencyState}
        for name, profile in profiles.items():
            assert profile["display_name"] == name
            assert profile["student_id"]
            assert profile["pace"] in pace_values
            assert profile["scaffolding_level"] in scaffold_values
            for competency_id, state in profile["competency_states"].items():
                assert competency_id in MEC271_NODE_IDS
                assert state in state_values

        assert profiles["Struggling Sam"]["scaffolding_level"] == "HIGH"
        assert profiles["Struggling Sam"]["pace"] == "STRUGGLING"
        assert profiles["Progressing Pat"]["scaffolding_level"] == "MEDIUM"
        assert profiles["Mastering Morgan"]["scaffolding_level"] == "LOW"
        assert profiles["Mastering Morgan"]["pace"] == "FAST"

    def test_demo_telemetry_samples_are_valid_structures(self) -> None:
        samples = get_demo_telemetry_samples()
        assert set(samples) == {"unstable", "underdamped", "well_tuned"}
        for key, sample in samples.items():
            MetricEvidence(**sample["metrics"])
            PIDGains(**sample["gains"])
            StepResponseTelemetry(**sample["metrics"])

        unstable = StepResponseTelemetry(**samples["unstable"]["metrics"])
        underdamped = StepResponseTelemetry(**samples["underdamped"]["metrics"])
        well_tuned = StepResponseTelemetry(**samples["well_tuned"]["metrics"])
        assert (
            diagnose_misconception(unstable)
            is PIDMisconception.UNSTABLE_TUNING
        )
        assert (
            diagnose_misconception(underdamped)
            is PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING
        )
        assert diagnose_misconception(well_tuned) is PIDMisconception.NONE