"""Tests for RoboticsEvidenceIngestor telemetry ingestion integration."""

import pytest

from ai_education.domain.enums import CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.robotics import (
    RoboticsEvidenceIngestor,
    StepResponseTelemetry,
    TelemetryThresholds,
)

INGESTOR = RoboticsEvidenceIngestor()
COMPETENCY_ID = "MEC271-PID-TUNE"


def fresh_manager() -> StudentModelManager:
    return StudentModelManager.create_new_student("robotics-student")


def passing_telemetry() -> StepResponseTelemetry:
    return StepResponseTelemetry(
        overshoot_pct=8.0,
        settling_time_sec=1.2,
        rise_time_sec=0.4,
        steady_state_error=0.005,
    )


class TestEvaluateTelemetry:
    def test_default_thresholds(self) -> None:
        thresholds = TelemetryThresholds()

        assert thresholds.max_overshoot_pct == 10.0
        assert thresholds.max_settling_time_sec == 2.0
        assert thresholds.max_steady_state_error == 0.02
        assert thresholds.require_stable is True

    def test_passing_telemetry_evaluates_true_with_summary(self) -> None:
        passed, summary = INGESTOR.evaluate_telemetry(
            passing_telemetry(), TelemetryThresholds()
        )

        assert passed is True
        assert summary.startswith("step response PASSED")
        assert "overshoot 8.0%" in summary
        assert "settling time 1.20s" in summary
        assert "steady-state error 0.0050" in summary

    def test_overshoot_failure_reports_metric_log(self) -> None:
        failing = passing_telemetry().model_copy(
            update={"overshoot_pct": 15.0}
        )

        passed, summary = INGESTOR.evaluate_telemetry(failing, TelemetryThresholds())

        assert passed is False
        assert summary.startswith("step response FAILED")
        assert "overshoot 15.0% exceeds max 10.0%" in summary

    def test_settling_time_failure_reports_metric_log(self) -> None:
        failing = passing_telemetry().model_copy(
            update={"settling_time_sec": 2.7}
        )

        passed, summary = INGESTOR.evaluate_telemetry(failing, TelemetryThresholds())

        assert passed is False
        assert "settling time 2.70s exceeds max 2.00s" in summary

    def test_steady_state_error_failure_reports_metric_log(self) -> None:
        failing = passing_telemetry().model_copy(
            update={"steady_state_error": 0.08}
        )

        passed, summary = INGESTOR.evaluate_telemetry(failing, TelemetryThresholds())

        assert passed is False
        assert "steady-state error 0.0800 exceeds max 0.0200" in summary

    def test_unstable_system_fails_even_within_metric_bounds(self) -> None:
        unstable = passing_telemetry().model_copy(update={"is_stable": False})

        passed, summary = INGESTOR.evaluate_telemetry(unstable, TelemetryThresholds())

        assert passed is False
        assert "system was not stable" in summary

    def test_custom_thresholds_relax_acceptance(self) -> None:
        telemetry = passing_telemetry().model_copy(update={"overshoot_pct": 15.0})
        relaxed = TelemetryThresholds(max_overshoot_pct=20.0)

        passed, summary = INGESTOR.evaluate_telemetry(telemetry, relaxed)

        assert passed is True
        assert "PASSED" in summary
        assert "overshoot 15.0%" in summary


class TestIngestAndRecord:
    def test_passing_telemetry_records_pass_evidence_and_advances_state(self) -> None:
        manager = fresh_manager()

        evidence = INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=passing_telemetry(),
            thresholds=TelemetryThresholds(),
            manager=manager,
        )

        assert evidence.task_id == COMPETENCY_ID
        assert evidence.attempt == 1
        assert evidence.stable is True
        assert evidence.requirements_met is True
        assert evidence.result == "PASS"
        assert evidence.metrics.overshoot == 8.0
        assert evidence.metrics.settling_time == 1.2
        assert evidence.metrics.steady_state_error == 0.005
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING

    def test_failing_telemetry_records_fail_evidence_without_progress(self) -> None:
        manager = fresh_manager()
        failing = passing_telemetry().model_copy(update={"overshoot_pct": 15.0})

        passed, summary = INGESTOR.evaluate_telemetry(failing, TelemetryThresholds())
        evidence = INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=failing,
            thresholds=TelemetryThresholds(),
            manager=manager,
        )

        assert passed is False
        assert "overshoot 15.0%" in summary
        assert evidence.requirements_met is False
        assert evidence.result == "FAIL"
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.NOT_DEMONSTRATED

    def test_unstable_telemetry_records_fail_evidence(self) -> None:
        manager = fresh_manager()
        unstable = passing_telemetry().model_copy(update={"is_stable": False})

        evidence = INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=unstable,
            thresholds=TelemetryThresholds(),
            manager=manager,
        )

        assert evidence.stable is False
        assert evidence.requirements_met is False
        assert evidence.result == "FAIL"
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.NOT_DEMONSTRATED

    def test_attempts_increment_across_ingests(self) -> None:
        manager = fresh_manager()

        first = INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=passing_telemetry(),
            thresholds=TelemetryThresholds(),
            manager=manager,
        )
        second = INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=passing_telemetry(),
            thresholds=TelemetryThresholds(),
            manager=manager,
        )

        assert first.attempt == 1
        assert second.attempt == 2
        assert len(manager.profile.competencies[COMPETENCY_ID].evidence_history) == 2


class TestFullProgression:
    def test_not_demonstrated_to_demonstrated_across_two_passes(self) -> None:
        manager = fresh_manager()

        assert manager.get_state(COMPETENCY_ID) is CompetencyState.NOT_DEMONSTRATED

        INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=passing_telemetry(),
            thresholds=TelemetryThresholds(),
            manager=manager,
        )
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING

        stronger_telemetry = passing_telemetry().model_copy(
            update={"overshoot_pct": 5.0, "settling_time_sec": 0.9}
        )
        INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=stronger_telemetry,
            thresholds=TelemetryThresholds(),
            manager=manager,
        )
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEMONSTRATED

    def test_mixed_passes_and_failures(self) -> None:
        manager = fresh_manager()
        failing = passing_telemetry().model_copy(update={"overshoot_pct": 30.0})

        INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=failing,
            thresholds=TelemetryThresholds(),
            manager=manager,
        )
        INGESTOR.ingest_and_record(
            student_id="robotics-student",
            competency_id=COMPETENCY_ID,
            telemetry=passing_telemetry(),
            thresholds=TelemetryThresholds(),
            manager=manager,
        )

        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING