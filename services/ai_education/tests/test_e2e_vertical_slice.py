"""End-to-end vertical slice tests over the AI Education gateway.

These tests drive the full educational pipeline from the HTTP layer down
through the domain engines and back. Telemetry submissions mutate the
persistent ``StudentModelManager`` through the API; the mastery, transfer,
and fluency engines then run against that same live state, confirming the
vertical slice holds together across every layer. No network or real LLM is
ever touched - the coach provider is a deterministic ``MockLLMProvider``.
"""

from fastapi.testclient import TestClient

from ai_education.api.app import create_app
from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.fluency import (
    AIFluencyEngine,
    AIFluencyReport,
    FluencyLevel,
)
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider
from ai_education.mastery import MasteryDeterminationEngine
from ai_education.reasoning import PIDMisconception
from ai_education.strategy import LearningPace, ScaffoldingLevel
from ai_education.transfer import (
    TransferAssessmentEngine,
    TransferEvaluationResult,
    get_transfer_scenario,
)

COMPETENCY_ID = "MEC271-PID-TUNE"

PASSING_TELEMETRY = {
    "metrics": {
        "overshoot_pct": 8.0,
        "settling_time_sec": 1.2,
        "rise_time_sec": 0.4,
        "steady_state_error": 0.005,
    },
    "gains": {"kp": 2.0, "ki": 0.5, "kd": 0.8},
}


def clean_client(student_id: str, responses=None):
    """Build a fresh gateway app wired to a clean student + mock LLM."""
    manager = StudentModelManager.create_new_student(student_id)
    llm_provider = MockLLMProvider(
        LLMConfig(provider_type="mock", model_name="api-e2e"),
        responses=list(responses or []),
    )
    client = TestClient(
        create_app(student_manager=manager, llm_provider=llm_provider)
    )
    return manager, client


def submit_telemetry(client, student_id, competency_id, body) -> dict:
    """POST one telemetry run and surface the structured response."""
    response = client.post(
        "/evidence/telemetry",
        json={"student_id": student_id, "competency_id": competency_id, **body},
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestStrugglingStudentRemediationLifecycle:
    def test_struggling_student_remediation_lifecycle(self) -> None:
        student_id = "e2e-struggling"
        manager, client = clean_client(
            student_id,
            responses=[
                "Rebuild the proportional gain concept: the overshoot and "
                "instability indicate the gain is far too high."
            ],
        )

        # 1. Bad telemetry: Kp=25, high overshoot, unstable system.
        bad = submit_telemetry(
            client,
            student_id,
            COMPETENCY_ID,
            {
                "metrics": {
                    "overshoot_pct": 30.0,
                    "settling_time_sec": 3.5,
                    "rise_time_sec": 0.8,
                    "steady_state_error": 0.10,
                    "is_stable": False,
                },
                "gains": {"kp": 25.0, "ki": 0.0, "kd": 0.0},
            },
        )

        assert bad["evidence_id"]
        assert bad["diagnosed_misconception"] in {
            PIDMisconception.UNSTABLE_TUNING.value,
            PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN.value,
        }
        assert bad["recommended_mode"] == CoachMode.PRACTICE.value
        assert (
            bad["updated_competency_state"]
            == CompetencyState.NOT_DEMONSTRATED.value
        )
        assert (
            manager.profile.competencies[COMPETENCY_ID]
            .evidence_history[0]
            .parameters.kp
            == 25.0
        )

        # 2. The profile reflects a struggling learner needing high scaffolding.
        profile = client.get(f"/student/{student_id}/profile")
        assert profile.status_code == 200
        body = profile.json()
        assert body["learning_pace"] == LearningPace.STRUGGLING.value
        assert body["scaffolding_level"] == ScaffoldingLevel.HIGH.value

        # 3. Coach chat surfaces remediation guidance under high scaffolding.
        chat = client.post(
            "/coach/chat",
            json={
                "student_id": student_id,
                "competency_id": COMPETENCY_ID,
                "user_message": "My system blew up. What do I fix?",
                "mode": CoachMode.REMEDIATE.value,
            },
        )
        assert chat.status_code == 200, chat.text
        chat_body = chat.json()
        assert chat_body["active_mode"] == CoachMode.REMEDIATE.value
        assert chat_body["scaffolding_level"] == ScaffoldingLevel.HIGH.value
        assert "rebuild" in chat_body["coach_message"].lower()
        assert "gain" in chat_body["coach_message"].lower()

        # 4. Fixed telemetry recovers the competency toward demonstration.
        fixed = submit_telemetry(
            client, student_id, COMPETENCY_ID, PASSING_TELEMETRY
        )
        assert (
            fixed["updated_competency_state"]
            == CompetencyState.DEVELOPING.value
        )
        demonstrated = submit_telemetry(
            client, student_id, COMPETENCY_ID, PASSING_TELEMETRY
        )
        assert (
            demonstrated["updated_competency_state"]
            == CompetencyState.DEMONSTRATED.value
        )

        # 5. The learner's pace has recovered from STRUGGLING to NORMAL.
        recovered = client.get(f"/student/{student_id}/profile")
        assert recovered.status_code == 200
        assert (
            recovered.json()["learning_pace"] == LearningPace.NORMAL.value
        )


class TestMasteryToTransferFlow:
    def test_mastery_to_transfer_e2e_flow(self) -> None:
        student_id = "e2e-mastery"
        manager, client = clean_client(student_id)

        # 1. Two consecutive passing telemetry runs through the API.
        first = submit_telemetry(
            client, student_id, COMPETENCY_ID, PASSING_TELEMETRY
        )
        second = submit_telemetry(
            client, student_id, COMPETENCY_ID, PASSING_TELEMETRY
        )
        assert (
            first["updated_competency_state"]
            == CompetencyState.DEVELOPING.value
        )
        assert (
            second["updated_competency_state"]
            == CompetencyState.DEMONSTRATED.value
        )
        assert second["recommended_mode"] == CoachMode.TRANSFER.value

        # 2. Formal mastery evaluation promotes the node to MASTERED.
        mastery = MasteryDeterminationEngine().evaluate_mastery(
            student_id, COMPETENCY_ID, manager
        )
        assert mastery.is_mastered is True
        assert mastery.consecutive_passes == 2
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.MASTERED

        profile = client.get(f"/student/{student_id}/profile")
        assert profile.status_code == 200
        assert profile.json()["mastered_count"] == 1
        assert COMPETENCY_ID in profile.json()["completed_competency_ids"]

        # 3. Request the industrial_oven cross-domain transfer prompt.
        transfer_engine = TransferAssessmentEngine()
        prompt = transfer_engine.generate_transfer_prompt(
            student_id, COMPETENCY_ID, scenario_id="industrial_oven"
        )
        assert prompt["scenario_id"] == "industrial_oven"
        assert prompt["domain"] == "thermal"
        assert "thermal inertia" in prompt["prompt"]

        # 4. Submit a generalizing explanation; transfer evaluation succeeds.
        explanation = (
            "Thermal inertia makes temperature lag the burner, so the "
            "integral term keeps accumulating until the delay lets the "
            "setpoint catch up to the commanded temperature."
        )
        scenario = get_transfer_scenario("industrial_oven")
        transfer = transfer_engine.evaluate_transfer_response(
            student_id, COMPETENCY_ID, explanation, scenario
        )
        assert isinstance(transfer, TransferEvaluationResult)
        assert transfer.is_transfer_successful is True
        assert transfer.score > 0.5
        assert "thermal" in transfer.feedback

        # 5. AI fluency report over the prompt + verification trail.
        prompt_history = [
            "Tune Kp=2.0, Ki=0.5, Kd=0.8 so the overshoot stays below 5% "
            "and settling time below 2 seconds.",
            "Compare the step response after retuning to those gains.",
            explanation,
        ]
        telemetry_verified = [True, True]  # both API runs passed
        report = AIFluencyEngine().generate_fluency_report(
            student_id, prompt_history, telemetry_verified
        )
        assert isinstance(report, AIFluencyReport)
        assert report.student_id == student_id
        assert report.metrics.critical_verification_score == 1.0
        assert report.metrics.autonomy_score > 0.0
        assert report.metrics.fluency_level in {
            FluencyLevel.COMPETENT,
            FluencyLevel.PROFICIENT,
            FluencyLevel.EXPERT,
        }
        assert report.recommendations