"""Tests for AdaptiveStrategyEngine pace, scaffolding, and plan generation."""

import pytest

from ai_education.domain.enums import CoachMode
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning import EvidenceReasoningEngine
from ai_education.robotics import (
    RoboticsEvidenceIngestor,
    StepResponseTelemetry,
    TelemetryThresholds,
)
from ai_education.strategy import (
    AdaptiveStrategyEngine,
    AdaptiveStrategyPlan,
    LearningPace,
    ScaffoldingLevel,
    evaluate_pace,
    evaluate_scaffolding_level,
)

ENGINE = AdaptiveStrategyEngine()
REASONING = EvidenceReasoningEngine()
INGESTOR = RoboticsEvidenceIngestor()
COMPETENCY_ID = "MEC271-PID-TUNE"
STUDENT_ID = "strategy-student"


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


def ingest(manager: StudentModelManager, t: StepResponseTelemetry) -> None:
    INGESTOR.ingest_and_record(
        student_id=STUDENT_ID,
        competency_id=COMPETENCY_ID,
        telemetry=t,
        thresholds=TelemetryThresholds(),
        manager=manager,
    )


class TestPaceEvaluation:
    def test_no_attempts_is_normal_pace(self) -> None:
        assert evaluate_pace(
            total_attempts=0, total_failures=0, competencies_attempted=0
        ) is LearningPace.NORMAL

    def test_high_failure_rate_is_struggling(self) -> None:
        assert evaluate_pace(
            total_attempts=4, total_failures=3, competencies_attempted=2
        ) is LearningPace.STRUGGLING

    def test_consecutive_failures_is_struggling(self) -> None:
        assert evaluate_pace(
            total_attempts=2,
            total_failures=2,
            competencies_attempted=1,
            consecutive_failures=2,
        ) is LearningPace.STRUGGLING

    def test_single_failure_is_normal(self) -> None:
        assert evaluate_pace(
            total_attempts=4, total_failures=1, competencies_attempted=2
        ) is LearningPace.NORMAL

    def test_clean_single_attempt_per_competency_is_fast(self) -> None:
        assert evaluate_pace(
            total_attempts=2, total_failures=0, competencies_attempted=2
        ) is LearningPace.FAST

    def test_multi_attempt_passes_are_normal_not_fast(self) -> None:
        assert evaluate_pace(
            total_attempts=4, total_failures=0, competencies_attempted=2
        ) is LearningPace.NORMAL


class TestScaffoldingEvaluation:
    def test_struggling_maps_to_high(self) -> None:
        assert (
            evaluate_scaffolding_level(LearningPace.STRUGGLING)
            is ScaffoldingLevel.HIGH
        )

    def test_fast_maps_to_low(self) -> None:
        assert evaluate_scaffolding_level(LearningPace.FAST) is ScaffoldingLevel.LOW

    def test_normal_maps_to_medium(self) -> None:
        assert (
            evaluate_scaffolding_level(LearningPace.NORMAL)
            is ScaffoldingLevel.MEDIUM
        )


class TestFreshStudentPlan:
    def test_fresh_student_plan_structure(self) -> None:
        plan = ENGINE.generate_strategy_plan(
            STUDENT_ID, fresh_manager(), REASONING
        )

        assert isinstance(plan, AdaptiveStrategyPlan)
        assert plan.student_id == STUDENT_ID
        assert plan.current_pace is LearningPace.NORMAL
        assert plan.scaffolding_level is ScaffoldingLevel.MEDIUM
        assert plan.recommended_target_node_id == "MEC271-FB"
        assert plan.recommended_mode is CoachMode.LEARN
        assert "NORMAL" in plan.strategy_notes
        assert "MEDIUM" in plan.strategy_notes

    def test_mismatched_student_id_raises(self) -> None:
        with pytest.raises(ValueError):
            ENGINE.generate_strategy_plan("someone-else", fresh_manager(), REASONING)


class TestFastLearnerPlan:
    def test_clean_multi_competency_passes_are_fast_low(self) -> None:
        manager = fresh_manager()
        # Pass two different competencies with a single attempt each.
        for node_id in ["MEC271-FB", "MEC271-PID-FUND"]:
            INGESTOR.ingest_and_record(
                student_id=STUDENT_ID,
                competency_id=node_id,
                telemetry=telemetry(),
                thresholds=TelemetryThresholds(),
                manager=manager,
            )

        plan = ENGINE.generate_strategy_plan(STUDENT_ID, manager, REASONING)

        assert plan.current_pace is LearningPace.FAST
        assert plan.scaffolding_level is ScaffoldingLevel.LOW
        assert plan.recommended_mode is CoachMode.PRACTICE


class TestStrugglingLearnerPlan:
    def _struggling_manager(self) -> StudentModelManager:
        """Fail the first target (MEC271-FB) twice to force remediation."""
        manager = fresh_manager()
        for _ in range(2):
            INGESTOR.ingest_and_record(
                student_id=STUDENT_ID,
                competency_id="MEC271-FB",
                telemetry=telemetry(overshoot_pct=30.0),
                thresholds=TelemetryThresholds(),
                manager=manager,
            )
        return manager

    def test_repeated_failures_recommend_high_scaffolding_remediate(self) -> None:
        manager = self._struggling_manager()

        plan = ENGINE.generate_strategy_plan(STUDENT_ID, manager, REASONING)

        assert plan.current_pace is LearningPace.STRUGGLING
        assert plan.scaffolding_level is ScaffoldingLevel.HIGH
        assert plan.recommended_target_node_id == "MEC271-FB"
        assert plan.recommended_mode is CoachMode.REMEDIATE

    def test_high_scaffolding_writes_directive_note(self) -> None:
        manager = self._struggling_manager()

        plan = ENGINE.generate_strategy_plan(STUDENT_ID, manager, REASONING)

        assert "HIGH" in plan.strategy_notes
        assert "MEC271-FB" in plan.strategy_notes


class TestScaffoldingPromptDirectives:
    def test_high_scaffolding_expands_prompt_directives(self) -> None:
        """High scaffolding adds a directive line; low scaffolding does not."""
        high_lines = strategy_directives(ScaffoldingLevel.HIGH)
        low_lines = strategy_directives(ScaffoldingLevel.LOW)

        assert any("step-by-step" in line.lower() for line in high_lines)
        assert not any("step-by-step" in line.lower() for line in low_lines)


def strategy_directives(level: ScaffoldingLevel) -> list[str]:
    """Mirror how a scaffolding level would adjust prompt directives."""
    base = ["Present the concept clearly", "End with a check-in question"]
    if level is ScaffoldingLevel.HIGH:
        base.append("Provide step-by-step guidance and frequent check-ins")
    if level is ScaffoldingLevel.LOW:
        base.append("Challenge the student with open-ended problems")
    return base