"""Tests for MasteryDeterminationEngine and mastery rules."""

import pytest

from ai_education.domain.enums import CompetencyState
from ai_education.domain.evidence import (
    PIDParameters,
    PracticalEvidence,
    SimulationMetrics,
)
from ai_education.domain.student import StudentModelManager
from ai_education.mastery import (
    MasteryDeterminationEngine,
    MasteryEvaluationResult,
    MasteryRuleConfig,
    check_evidence_consistency,
)

ENGINE = MasteryDeterminationEngine()
COMPETENCY_ID = "MEC271-PID-TUNE"
PARENT_ID = "MEC271-PID-REASON"
STUDENT_ID = "mastery-student"
DEFAULT_CONFIG = MasteryRuleConfig()


def fresh_manager() -> StudentModelManager:
    return StudentModelManager.create_new_student(STUDENT_ID)


def make_evidence(requirements_met: bool, attempt: int, overshoot: float = 3.0) -> PracticalEvidence:
    return PracticalEvidence(
        task_id="PID-TUNE",
        attempt=attempt,
        parameters=PIDParameters(kp=1.2, ki=0.5, kd=0.15),
        metrics=SimulationMetrics(
            overshoot=overshoot,
            settling_time=1.2,
            steady_state_error=0.005,
        ),
        stable=True,
        requirements_met=requirements_met,
        result="PASS" if requirements_met else "FAIL",
    )


def record_attempt(manager: StudentModelManager, requirements_met: bool, attempt: int) -> None:
    manager.record_evidence(COMPETENCY_ID, make_evidence(requirements_met, attempt))


def evaluate(
    manager: StudentModelManager,
    config: MasteryRuleConfig = DEFAULT_CONFIG,
    competency_id: str = COMPETENCY_ID,
) -> MasteryEvaluationResult:
    return ENGINE.evaluate_mastery(STUDENT_ID, competency_id, manager, config)


class TestEvidenceConsistency:
    def test_empty_history_is_not_consistent(self) -> None:
        assert check_evidence_consistency([], min_passes=2) is False

    def test_single_pass_below_minimum(self) -> None:
        history = [make_evidence(True, 1)]
        assert check_evidence_consistency(history, min_passes=2) is False

    def test_two_consecutive_passes_are_consistent(self) -> None:
        history = [make_evidence(True, 1), make_evidence(True, 2)]
        assert check_evidence_consistency(history, min_passes=2) is True

    def test_failure_before_passes_keeps_tail_consistent(self) -> None:
        history = [
            make_evidence(False, 1),
            make_evidence(True, 2),
            make_evidence(True, 3),
        ]
        assert check_evidence_consistency(history, min_passes=2) is True

    def test_failure_after_pass_breaks_the_tail(self) -> None:
        history = [
            make_evidence(True, 1),
            make_evidence(False, 2),
            make_evidence(True, 3),
        ]
        assert check_evidence_consistency(history, min_passes=2) is False


class TestSinglePassInsufficient:
    def test_one_pass_does_not_master(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)

        result = evaluate(manager)

        assert isinstance(result, MasteryEvaluationResult)
        assert result.student_id == STUDENT_ID
        assert result.competency_id == COMPETENCY_ID
        assert result.is_mastered is False
        assert result.consecutive_passes == 1
        assert "Not mastered" in result.reason
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING


class TestTwoPassesMaster:
    def test_two_consecutive_passes_trigger_mastered(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)
        record_attempt(manager, True, 2)

        result = evaluate(manager)

        assert result.is_mastered is True
        assert result.consecutive_passes == 2
        assert "Mastered" in result.reason
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.MASTERED

    def test_mastery_is_sticky_under_new_evidence(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)
        record_attempt(manager, True, 2)
        evaluate(manager)

        record_attempt(manager, False, 3)

        assert manager.get_state(COMPETENCY_ID) is CompetencyState.MASTERED


class TestFailureResets:
    def test_failure_after_pass_resets_consecutive_count(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)
        record_attempt(manager, False, 2)

        result = evaluate(manager)

        assert result.consecutive_passes == 0
        assert result.is_mastered is False
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEVELOPING

    def test_failure_then_single_pass_is_still_insufficient(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)
        record_attempt(manager, False, 2)
        record_attempt(manager, True, 3)

        result = evaluate(manager)

        assert result.consecutive_passes == 1
        assert result.is_mastered is False
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.DEMONSTRATED


class TestPrerequisiteAlignment:
    def test_parent_unearned_blocks_mastery_when_required(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)
        record_attempt(manager, True, 2)

        result = evaluate(
            manager, MasteryRuleConfig(require_prerequisites_mastered=True)
        )

        assert result.is_mastered is False
        assert PARENT_ID in result.reason
        assert manager.get_state(COMPETENCY_ID) is not CompetencyState.MASTERED

    def test_parent_unearned_does_not_block_by_default(self) -> None:
        manager = fresh_manager()
        record_attempt(manager, True, 1)
        record_attempt(manager, True, 2)

        result = evaluate(manager)

        assert result.is_mastered is True
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.MASTERED

    def test_mastered_parent_permits_mastery(self) -> None:
        manager = fresh_manager()
        for _ in range(2):
            manager.record_evidence(PARENT_ID, make_evidence(True, 1))
        evaluate(manager, competency_id=PARENT_ID)
        assert manager.get_state(PARENT_ID) is CompetencyState.MASTERED

        record_attempt(manager, True, 1)
        record_attempt(manager, True, 2)
        result = evaluate(
            manager, MasteryRuleConfig(require_prerequisites_mastered=True)
        )

        assert result.is_mastered is True
        assert manager.get_state(COMPETENCY_ID) is CompetencyState.MASTERED


class TestGuardrails:
    def test_mismatched_student_id_raises(self) -> None:
        manager = fresh_manager()
        with pytest.raises(ValueError):
            ENGINE.evaluate_mastery("someone-else", COMPETENCY_ID, manager)

    def test_unknown_competency_raises(self) -> None:
        manager = fresh_manager()
        with pytest.raises(KeyError):
            ENGINE.evaluate_mastery(STUDENT_ID, "MEC271-UNKNOWN", manager)