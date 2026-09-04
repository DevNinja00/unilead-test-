"""Tests for the FastAPI gateway router and application factory."""

from fastapi.testclient import TestClient

from ai_education.api import (
    ChatResponse,
    StudentProfileResponse,
    TelemetrySubmissionResponse,
)
from ai_education.api.app import create_app
from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider
from ai_education.reasoning import PIDMisconception
from ai_education.strategy import LearningPace, ScaffoldingLevel


def make_client(student_id: str = "gateway-student", responses=None):
    manager = StudentModelManager.create_new_student(student_id)
    provider = MockLLMProvider(
        LLMConfig(provider_type="mock", model_name="api-test"),
        responses=list(responses or []),
    )
    client = TestClient(create_app(student_manager=manager, llm_provider=provider))
    return client, manager


class TestHealth:
    def test_health_returns_ok(self) -> None:
        client, _ = make_client()

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "ai-education-gateway"


class TestCoachChat:
    def test_chat_returns_structured_response(self) -> None:
        client, _ = make_client(responses=["Let's learn feedback first."])

        response = client.post(
            "/coach/chat",
            json={
                "student_id": "gateway-student",
                "competency_id": "MEC271-FB",
                "user_message": "Help me start",
            },
        )

        assert response.status_code == 200
        payload = ChatResponse.model_validate(response.json())
        assert payload.student_id == "gateway-student"
        assert payload.coach_message == "Let's learn feedback first."
        assert payload.active_mode is CoachMode.LEARN
        assert payload.scaffolding_level is ScaffoldingLevel.MEDIUM

    def test_chat_with_explicit_mode_is_respected(self) -> None:
        client, _ = make_client(responses=["Try changing the proportional gain."])

        response = client.post(
            "/coach/chat",
            json={
                "student_id": "gateway-student",
                "competency_id": "MEC271-PID-TUNE",
                "user_message": "What should I change?",
                "mode": "PRACTICE",
            },
        )

        assert response.status_code == 200
        payload = ChatResponse.model_validate(response.json())
        assert payload.active_mode is CoachMode.PRACTICE

    def test_chat_unknown_student_returns_404(self) -> None:
        client, _ = make_client()

        response = client.post(
            "/coach/chat",
            json={
                "student_id": "nobody",
                "competency_id": "MEC271-FB",
                "user_message": "hi",
            },
        )

        assert response.status_code == 404


class TestTelemetry:
    def test_unstable_telemetry_diagnoses_misconception(self) -> None:
        client, manager = make_client()

        response = client.post(
            "/evidence/telemetry",
            json={
                "student_id": "gateway-student",
                "competency_id": "MEC271-PID-TUNE",
                "metrics": {
                    "overshoot_pct": 8.0,
                    "settling_time_sec": 1.2,
                    "rise_time_sec": 0.4,
                    "steady_state_error": 0.005,
                    "is_stable": False,
                },
                "gains": {"kp": 5.0, "ki": 0.0, "kd": 0.0},
            },
        )

        assert response.status_code == 200
        payload = TelemetrySubmissionResponse.model_validate(response.json())
        assert payload.evidence_id
        assert payload.diagnosed_misconception is PIDMisconception.UNSTABLE_TUNING
        assert payload.recommended_mode is CoachMode.PRACTICE
        assert payload.updated_competency_state is CompetencyState.NOT_DEMONSTRATED
        record = manager.profile.competencies["MEC271-PID-TUNE"]
        assert record.evidence_history[0].parameters.kp == 5.0
        assert record.evidence_history[0].requirements_met is False

    def test_passing_telemetry_advances_state_and_recommends_practice(self) -> None:
        client, manager = make_client()

        response = client.post(
            "/evidence/telemetry",
            json={
                "student_id": "gateway-student",
                "competency_id": "MEC271-PID-TUNE",
                "metrics": {
                    "overshoot_pct": 8.0,
                    "settling_time_sec": 1.2,
                    "rise_time_sec": 0.4,
                    "steady_state_error": 0.005,
                },
                "gains": {"kp": 1.2, "ki": 0.4, "kd": 0.1},
            },
        )

        assert response.status_code == 200
        payload = TelemetrySubmissionResponse.model_validate(response.json())
        assert payload.evidence_id
        assert payload.diagnosed_misconception is PIDMisconception.NONE
        assert payload.recommended_mode is CoachMode.PRACTICE
        assert payload.updated_competency_state is CompetencyState.DEVELOPING
        assert manager.get_state("MEC271-PID-TUNE") is CompetencyState.DEVELOPING

    def test_two_passes_demonstrate_and_recommend_transfer(self) -> None:
        client, _ = make_client()
        payload = {
            "student_id": "gateway-student",
            "competency_id": "MEC271-PID-TUNE",
            "metrics": {
                "overshoot_pct": 8.0,
                "settling_time_sec": 1.2,
                "rise_time_sec": 0.4,
                "steady_state_error": 0.005,
            },
            "gains": {"kp": 1.2, "ki": 0.4, "kd": 0.1},
        }

        client.post("/evidence/telemetry", json=payload)
        response = client.post("/evidence/telemetry", json=payload)

        assert response.status_code == 200
        second = TelemetrySubmissionResponse.model_validate(response.json())
        assert second.updated_competency_state is CompetencyState.DEMONSTRATED
        assert second.recommended_mode is CoachMode.TRANSFER

    def test_telemetry_unknown_competency_returns_404(self) -> None:
        client, _ = make_client()

        response = client.post(
            "/evidence/telemetry",
            json={
                "student_id": "gateway-student",
                "competency_id": "NOPE",
                "metrics": {
                    "overshoot_pct": 8.0,
                    "settling_time_sec": 1.2,
                    "rise_time_sec": 0.4,
                    "steady_state_error": 0.005,
                },
                "gains": {"kp": 1.0, "ki": 0.0, "kd": 0.0},
            },
        )

        assert response.status_code == 404


class TestProfile:
    def test_profile_fresh_student(self) -> None:
        client, _ = make_client()

        response = client.get("/student/gateway-student/profile")

        assert response.status_code == 200
        payload = StudentProfileResponse.model_validate(response.json())
        assert payload.student_id == "gateway-student"
        assert payload.course_id == "MEC271"
        assert payload.total_competencies == 5
        assert payload.demonstrated_count == 0
        assert payload.developing_count == 0
        assert payload.not_demonstrated_count == 5
        assert payload.mastered_count == 0
        assert payload.learning_pace is LearningPace.NORMAL
        assert payload.scaffolding_level is ScaffoldingLevel.MEDIUM
        assert payload.target_competency_id == "MEC271-FB"
        assert payload.completed_competency_ids == []

    def test_profile_reflects_ingested_evidence_and_target_shift(self) -> None:
        client, _ = make_client()
        passing = {
            "student_id": "gateway-student",
            "competency_id": "MEC271-FB",
            "metrics": {
                "overshoot_pct": 8.0,
                "settling_time_sec": 1.2,
                "rise_time_sec": 0.4,
                "steady_state_error": 0.005,
            },
            "gains": {"kp": 1.0, "ki": 0.5, "kd": 0.2},
        }

        client.post("/evidence/telemetry", json=passing)
        client.post("/evidence/telemetry", json=passing)
        response = client.get("/student/gateway-student/profile")

        assert response.status_code == 200
        payload = StudentProfileResponse.model_validate(response.json())
        assert payload.developing_count == 0
        assert payload.demonstrated_count == 1
        assert payload.not_demonstrated_count == 4
        assert payload.completed_competency_ids == ["MEC271-FB"]
        assert payload.target_competency_id == "MEC271-PID-FUND"

    def test_profile_unknown_student_returns_404(self) -> None:
        client, _ = make_client()

        response = client.get("/student/nobody/profile")

        assert response.status_code == 404