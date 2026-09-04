"""Tests for RemediationEngine strategy lookup and plan generation."""

import pytest

from ai_education.domain.student import StudentModelManager
from ai_education.reasoning import EvidenceReasoningEngine, PIDMisconception
from ai_education.remediation import (
    RemediationAction,
    RemediationEngine,
    RemediationPlan,
    get_remediation_strategy,
)
from ai_education.robotics import (
    RoboticsEvidenceIngestor,
    StepResponseTelemetry,
    TelemetryThresholds,
)

ENGINE = RemediationEngine()
REASONING = EvidenceReasoningEngine()
INGESTOR = RoboticsEvidenceIngestor()
COMPETENCY_ID = "MEC271-PID-TUNE"
PREREQ_ID = "MEC271-PID-REASON"
STUDENT_ID = "remediation-student"

ALL_MISCONCEPTIONS = list(PIDMisconception)

EXPECTED_ACTIONS = {
    PIDMisconception.UNSTABLE_TUNING: RemediationAction.RESET_EXPERIMENT,
    PIDMisconception.MISSING_INTEGRAL_ACTION: RemediationAction.EXPLAIN_CONCEPT,
    PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN: RemediationAction.ADJUST_PARAMETER_STEP,
    PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING: RemediationAction.REVIEW_PREREQUISITE,
    PIDMisconception.NONE: RemediationAction.EXPLAIN_CONCEPT,
}


def fresh_manager() -> StudentModelManager:
    return StudentModelManager.create_new_student(STUDENT_ID)


def telemetry(
    overshoot_pct: float = 8.0,
    settling_time_sec: float = 1.2,
    steady_state_error: float = 0.005,
    is_stable: bool = True,
) -> StepResponseTelemetry:
    return StepResponseTelemetry(
        overshoot_pct=overshoot_pct,
        settling_time_sec=settling_time_sec,
        rise_time_sec=0.4,
        steady_state_error=steady_state_error,
        is_stable=is_stable,
    )


def ingest_failure(manager: StudentModelManager, t: StepResponseTelemetry) -> None:
    INGESTOR.ingest_and_record(
        student_id=STUDENT_ID,
        competency_id=COMPETENCY_ID,
        telemetry=t,
        thresholds=TelemetryThresholds(),
        manager=manager,
    )


def build_plan(
    manager: StudentModelManager,
) -> RemediationPlan:
    return ENGINE.build_remediation_plan(
        STUDENT_ID, COMPETENCY_ID, manager, REASONING
    )


class TestStrategyLookup:
    @pytest.mark.parametrize("misconception", ALL_MISCONCEPTIONS)
    def test_every_misconception_has_full_strategy(
        self, misconception: PIDMisconception
    ) -> None:
        strategy = get_remediation_strategy(misconception)

        assert set(strategy) == {
            "action",
            "conceptual_focus",
            "diagnostic_question",
        }
        assert strategy["action"] in RemediationAction
        assert strategy["conceptual_focus"].strip()
        assert strategy["diagnostic_question"].strip()

    @pytest.mark.parametrize(
        "misconception, expected_action",
        [(m, EXPECTED_ACTIONS[m]) for m in ALL_MISCONCEPTIONS],
    )
    def test_action_mapping(
        self, misconception: PIDMisconception, expected_action: RemediationAction
    ) -> None:
        assert get_remediation_strategy(misconception)["action"] == expected_action


class TestPlanGeneration:
    def test_unstable_tuning_plan(self) -> None:
        manager = fresh_manager()
        ingest_failure(manager, telemetry(is_stable=False))

        plan = build_plan(manager)

        assert isinstance(plan, RemediationPlan)
        assert plan.student_id == STUDENT_ID
        assert plan.competency_id == COMPETENCY_ID
        assert plan.misconception is PIDMisconception.UNSTABLE_TUNING
        assert plan.action is RemediationAction.RESET_EXPERIMENT
        assert plan.remediation_steps
        assert any("unstable" in step.lower() for step in plan.remediation_steps)
        assert plan.guided_question == get_remediation_strategy(
            PIDMisconception.UNSTABLE_TUNING
        )["diagnostic_question"]

    def test_missing_integral_action_plan(self) -> None:
        manager = fresh_manager()
        ingest_failure(
            manager, telemetry(steady_state_error=0.4, overshoot_pct=10.0)
        )

        plan = build_plan(manager)

        assert plan.misconception is PIDMisconception.MISSING_INTEGRAL_ACTION
        assert plan.action is RemediationAction.EXPLAIN_CONCEPT
        assert any("integral" in step.lower() for step in plan.remediation_steps)

    def test_excessive_proportional_gain_plan(self) -> None:
        manager = fresh_manager()
        ingest_failure(manager, telemetry(overshoot_pct=40.0))

        plan = build_plan(manager)

        assert plan.misconception is PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN
        assert plan.action is RemediationAction.ADJUST_PARAMETER_STEP
        assert any("kp" in step.lower() for step in plan.remediation_steps)

    def test_insufficient_derivative_damping_plan(self) -> None:
        manager = fresh_manager()
        ingest_failure(
            manager,
            telemetry(overshoot_pct=10.0, settling_time_sec=3.0),
        )

        plan = build_plan(manager)

        assert plan.misconception is PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING
        assert plan.action is RemediationAction.REVIEW_PREREQUISITE
        assert any("kd" in step.lower() for step in plan.remediation_steps)

    def test_no_failure_plan_uses_general_strategy(self) -> None:
        manager = fresh_manager()
        INGESTOR.ingest_and_record(
            student_id=STUDENT_ID,
            competency_id=COMPETENCY_ID,
            telemetry=telemetry(),
            thresholds=TelemetryThresholds(),
            manager=manager,
        )

        plan = build_plan(manager)

        assert plan.misconception is PIDMisconception.NONE
        assert plan.action is RemediationAction.EXPLAIN_CONCEPT
        assert plan.remediation_steps


class TestIntegration:
    def test_mismatched_student_id_raises(self) -> None:
        manager = fresh_manager()
        with pytest.raises(ValueError):
            ENGINE.build_remediation_plan(
                "someone-else", COMPETENCY_ID, manager, REASONING
            )

    def test_unknown_competency_raises(self) -> None:
        manager = fresh_manager()
        with pytest.raises(KeyError):
            ENGINE.build_remediation_plan(
                STUDENT_ID, "MEC271-UNKNOWN", manager, REASONING
            )

    def test_unstable_plan_names_prerequisite_gap(self) -> None:
        manager = fresh_manager()
        ingest_failure(manager, telemetry(is_stable=False))

        plan = build_plan(manager)

        # MEC271-PID-REASON is a parent of the target and undemonstrated.
        assert any(PREREQ_ID in step for step in plan.remediation_steps)

    def test_plan_reflects_recorded_evidence_through_manager(self) -> None:
        manager = fresh_manager()
        ingest_failure(manager, telemetry(is_stable=False))

        plan = build_plan(manager)

        record = manager.profile.competencies[COMPETENCY_ID]
        assert len(record.evidence_history) == 1
        assert plan.misconception is PIDMisconception.UNSTABLE_TUNING
        assert REASONING.analyze_competency_evidence(
            STUDENT_ID, COMPETENCY_ID, manager
        ).detected_misconception is PIDMisconception.UNSTABLE_TUNING