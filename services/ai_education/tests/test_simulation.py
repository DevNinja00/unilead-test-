"""Tests for the built-in PID step-response simulation engine.

Covers the numerical simulator (stability, steady-state error, metrics,
determinism), its wiring into the existing evidence/ingestion loop, and the
new ``/evidence/simulate`` gateway route.
"""

from fastapi.testclient import TestClient

from ai_education.api.app import create_app
from ai_education.domain.enums import CompetencyState
from ai_education.domain.evidence import PIDParameters
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning import PIDMisconception
from ai_education.robotics import (
    RoboticsEvidenceIngestor,
    TelemetryThresholds,
)
from ai_education.simulation import PIDSimulationEngine

COMPETENCY_ID = "MEC271-PID-TUNE"
ENGINE = PIDSimulationEngine()
INGESTOR = RoboticsEvidenceIngestor()

TUNED = PIDParameters(kp=1.2, ki=3.0, kd=0.2)
OVER_TUNED = PIDParameters(kp=2.0, ki=12.0, kd=0.0)
PROPORTIONAL_ONLY = PIDParameters(kp=1.5, ki=0.0, kd=0.0)


def _make_client() -> tuple[TestClient, StudentModelManager]:
    manager = StudentModelManager.create_new_student("gateway-student")
    app = create_app(student_manager=manager)
    return TestClient(app), manager


class TestSimulatorNumerics:
    def test_tuned_gains_converge_and_pass_acceptance(self) -> None:
        telemetry = ENGINE.simulate_step(TUNED)

        assert telemetry.is_stable is True
        assert telemetry.overshoot_pct <= 10.0
        assert telemetry.settling_time_sec <= 2.0
        assert telemetry.steady_state_error <= 0.02

        passed, _summary = INGESTOR.evaluate_telemetry(
            telemetry, TelemetryThresholds()
        )
        assert passed is True

    def test_high_integral_gain_drives_unstable_limit_cycle(self) -> None:
        telemetry = ENGINE.simulate_step(OVER_TUNED)

        assert telemetry.is_stable is False
        passed, _summary = INGESTOR.evaluate_telemetry(
            telemetry, TelemetryThresholds()
        )
        assert passed is False

    def test_proportional_only_leaves_steady_state_error(self) -> None:
        telemetry = ENGINE.simulate_step(PROPORTIONAL_ONLY)

        assert telemetry.is_stable is True
        assert telemetry.steady_state_error > 0.02

    def test_metrics_are_self_consistent(self) -> None:
        telemetry = ENGINE.simulate_step(TUNED)

        assert 0.0 < telemetry.rise_time_sec < telemetry.settling_time_sec
        assert telemetry.overshoot_pct >= 0.0
        assert telemetry.settling_time_sec > 0.0

    def test_simulation_is_deterministic(self) -> None:
        first = ENGINE.simulate_step(TUNED)
        second = ENGINE.simulate_step(TUNED)

        assert first == second

    def test_step_samples_stream_like_a_sensor(self) -> None:
        samples = list(ENGINE.step_samples(TUNED, duration=1.0))

        assert len(samples) > 0
        start_time, start_output, _ = samples[0]
        assert start_time == 0.0
        assert start_output == 0.0
        # The stream ends near the requested horizon and settles toward 1.0.
        assert abs(samples[-1][0] - 1.0) < 0.05
        assert 0.5 < samples[-1][1] <= 1.2


class TestWiring:
    def test_simulated_runs_progress_student_state(self) -> None:
        manager = StudentModelManager.create_new_student("sim-student")

        first = ENGINE.simulate_step(TUNED)
        INGESTOR.ingest_and_record(
            "sim-student", COMPETENCY_ID, first, TelemetryThresholds(), manager
        )
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING

        second = ENGINE.simulate_step(TUNED)
        INGESTOR.ingest_and_record(
            "sim-student", COMPETENCY_ID, second, TelemetryThresholds(), manager
        )
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEMONSTRATED

    def test_unstable_run_diagnoses_unstable_tuning(self) -> None:
        from ai_education.reasoning import EvidenceReasoningEngine

        manager = StudentModelManager.create_new_student("sim-student")
        telemetry = ENGINE.simulate_step(OVER_TUNED)
        INGESTOR.ingest_and_record(
            "sim-student", COMPETENCY_ID, telemetry, TelemetryThresholds(), manager
        )

        summary = EvidenceReasoningEngine().analyze_competency_evidence(
            "sim-student", COMPETENCY_ID, manager
        )
        assert summary.detected_misconception is PIDMisconception.UNSTABLE_TUNING

    def test_proportional_only_run_diagnoses_missing_integral(self) -> None:
        from ai_education.reasoning import EvidenceReasoningEngine

        manager = StudentModelManager.create_new_student("sim-student")
        telemetry = ENGINE.simulate_step(PROPORTIONAL_ONLY)
        INGESTOR.ingest_and_record(
            "sim-student", COMPETENCY_ID, telemetry, TelemetryThresholds(), manager
        )

        summary = EvidenceReasoningEngine().analyze_competency_evidence(
            "sim-student", COMPETENCY_ID, manager
        )
        assert (
            summary.detected_misconception
            is PIDMisconception.MISSING_INTEGRAL_ACTION
        )


class TestSimulateEndpoint:
    def test_tuned_run_returns_telemetry_and_advances_state(self) -> None:
        client, manager = _make_client()

        response = client.post(
            "/evidence/simulate",
            json={
                "student_id": "gateway-student",
                "competency_id": COMPETENCY_ID,
                "gains": {"kp": 1.2, "ki": 3.0, "kd": 0.2},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["telemetry"]["is_stable"] is True
        assert payload["telemetry"]["overshoot_pct"] <= 10.0
        assert payload["diagnosed_misconception"] == "NONE"
        assert payload["updated_competency_state"] == "DEVELOPING"
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING

    def test_unstable_run_reports_misconception(self) -> None:
        client, _ = _make_client()

        response = client.post(
            "/evidence/simulate",
            json={
                "student_id": "gateway-student",
                "competency_id": COMPETENCY_ID,
                "gains": {"kp": 2.0, "ki": 12.0, "kd": 0.0},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["telemetry"]["is_stable"] is False
        assert payload["diagnosed_misconception"] == "UNSTABLE_TUNING"
        assert payload["updated_competency_state"] == "NOT_DEMONSTRATED"

    def test_unknown_student_returns_404(self) -> None:
        client, _ = _make_client()

        response = client.post(
            "/evidence/simulate",
            json={
                "student_id": "nobody",
                "competency_id": COMPETENCY_ID,
                "gains": {"kp": 1.2, "ki": 1.5, "kd": 0.15},
            },
        )

        assert response.status_code == 404