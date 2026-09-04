"""Tests for EvidenceReasoningEngine evidence synthesis and recommendations."""

import pytest

from ai_education.domain.enums import CoachMode, CompetencyState
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning import (
    EvidenceReasoningEngine,
    EvidenceReasoningSummary,
    PIDMisconception,
    diagnose_misconception,
)
from ai_education.robotics import (
    RoboticsEvidenceIngestor,
    StepResponseTelemetry,
    TelemetryThresholds,
)

ENGINE = EvidenceReasoningEngine()
INGESTOR = RoboticsEvidenceIngestor()
COMPETENCY_ID = "MEC271-PID-TUNE"


def fresh_manager() -> StudentModelManager:
    return StudentModelManager.create_new_student("reasoning-student")


def telemetry(
    overshoot_pct: float = 8.0,
    settling_time_sec: float = 1.2,
    steady_state_error: float = 0.005,
    is_stable: bool = True,
    rise_time_sec: float = 0.4,
) -> StepResponseTelemetry:
    return StepResponseTelemetry(
        overshoot_pct=overshoot_pct,
        settling_time_sec=settling_time_sec,
        rise_time_sec=rise_time_sec,
        steady_state_error=steady_state_error,
        is_stable=is_stable,
    )


def ingest(
    manager: StudentModelManager, t: StepResponseTelemetry
) -> None:
    INGESTOR.ingest_and_record(
        student_id="reasoning-student",
        competency_id=COMPETENCY_ID,
        telemetry=t,
        thresholds=TelemetryThresholds(),
        manager=manager,
    )


class TestMisconceptionDiagnosis:
    @pytest.mark.parametrize(
        "t,expected",
        [
            (telemetry(is_stable=False), PIDMisconception.UNSTABLE_TUNING),
            (
                telemetry(steady_state_error=0.09),
                PIDMisconception.MISSING_INTEGRAL_ACTION,
            ),
            (
                telemetry(overshoot_pct=30.0),
                PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN,
            ),
            (
                telemetry(settling_time_sec=2.5, overshoot_pct=15.0),
                PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING,
            ),
            (telemetry(), PIDMisconception.NONE),
        ],
    )
    def test_diagnosis_priorities(self, t: StepResponseTelemetry, expected) -> None:
        assert diagnose_misconception(t) is expected

    def test_unstable_wins_over_steady_state_error(self) -> None:
        t = telemetry(is_stable=False, steady_state_error=0.2)
        assert diagnose_misconception(t) is PIDMisconception.UNSTABLE_TUNING

    def test_steady_state_error_not_flagged_at_boundary(self) -> None:
        t = telemetry(steady_state_error=0.05)
        assert diagnose_misconception(t) is not PIDMisconception.MISSING_INTEGRAL_ACTION

    def test_overshoot_boundary_is_not_excessive(self) -> None:
        t = telemetry(overshoot_pct=25.0)
        assert diagnose_misconception(t) is not PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN

    def test_high_settling_without_overshoot_is_not_damping_issue(self) -> None:
        t = telemetry(settling_time_sec=3.0, overshoot_pct=0.0)
        assert diagnose_misconception(t) is PIDMisconception.NONE

    def test_defaults_diagnose_none(self) -> None:
        assert diagnose_misconception(telemetry()) is PIDMisconception.NONE


class TestFreshStudent:
    def test_new_student_recommends_learn(self) -> None:
        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, fresh_manager()
        )

        assert isinstance(summary, EvidenceReasoningSummary)
        assert summary.competency_id == COMPETENCY_ID
        assert summary.total_attempts == 0
        assert summary.consecutive_failures == 0
        assert summary.detected_misconception is PIDMisconception.NONE
        assert summary.recommended_mode is CoachMode.LEARN
        assert "no recorded attempts" in summary.summary_text

    def test_mismatched_student_id_raises(self) -> None:
        with pytest.raises(ValueError):
            ENGINE.analyze_competency_evidence(
                "someone-else", COMPETENCY_ID, fresh_manager()
            )


class TestFailingStudent:
    def test_single_failure_detects_misconception_and_practices(self) -> None:
        manager = fresh_manager()
        ingest(manager, telemetry(overshoot_pct=30.0))

        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, manager
        )

        assert summary.total_attempts == 1
        assert summary.consecutive_failures == 1
        assert (
            summary.detected_misconception
            is PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN
        )
        assert summary.recommended_mode is CoachMode.PRACTICE

    def test_two_consecutive_failures_recommend_remediate(self) -> None:
        manager = fresh_manager()
        ingest(manager, telemetry(overshoot_pct=30.0))
        ingest(manager, telemetry(steady_state_error=0.4))

        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, manager
        )

        assert summary.consecutive_failures == 2
        assert (
            summary.detected_misconception is PIDMisconception.MISSING_INTEGRAL_ACTION
        )
        assert summary.recommended_mode is CoachMode.REMEDIATE
        assert "REMEDIATE" in summary.summary_text

    def test_interleaved_pass_resets_consecutive_failure_count(self) -> None:
        manager = fresh_manager()
        ingest(manager, telemetry(overshoot_pct=30.0))
        ingest(manager, telemetry())
        ingest(manager, telemetry(steady_state_error=0.3))

        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, manager
        )

        assert summary.total_attempts == 3
        assert summary.consecutive_failures == 1
        assert summary.recommended_mode is CoachMode.PRACTICE

    def test_unstable_latest_failure_recommends_remediate(self) -> None:
        manager = fresh_manager()
        ingest(manager, telemetry(overshoot_pct=30.0))
        ingest(manager, telemetry(is_stable=False))

        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, manager
        )

        assert summary.consecutive_failures == 2
        assert summary.detected_misconception is PIDMisconception.UNSTABLE_TUNING
        assert summary.recommended_mode is CoachMode.REMEDIATE


class TestMasteringStudent:
    def test_demonstrated_recommends_transfer(self) -> None:
        manager = fresh_manager()
        ingest(manager, telemetry())
        ingest(manager, telemetry(overshoot_pct=5.0, settling_time_sec=0.8))

        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, manager
        )

        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEMONSTRATED
        assert summary.detected_misconception is PIDMisconception.NONE
        assert summary.recommended_mode is CoachMode.TRANSFER

    def test_two_passes_recommend_transfer_with_empty_summary(self) -> None:
        manager = fresh_manager()
        ingest(manager, telemetry())
        ingest(manager, telemetry())

        summary = ENGINE.analyze_competency_evidence(
            "reasoning-student", COMPETENCY_ID, manager
        )

        assert summary.total_attempts == 2
        assert summary.consecutive_failures == 0
        assert summary.recommended_mode is CoachMode.TRANSFER
        assert "TRANSFER" in summary.summary_text