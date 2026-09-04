"""Unit tests for the StudentModelManager."""

import pytest

from ai_education.domain.courses.mec271 import MEC271_NODE_IDS
from ai_education.domain.enums import CompetencyState
from ai_education.domain.evidence import PracticalEvidence
from ai_education.domain.student import StudentModelManager


def make_evidence(attempt: int, requirements_met: bool = True, result: str = "PASS"):
    return PracticalEvidence.model_validate(
        {
            "task_id": "PID-001",
            "attempt": attempt,
            "parameters": {"kp": 2.0, "ki": 0.5, "kd": 0.25},
            "metrics": {
                "overshoot": 5.2,
                "settling_time": 3.4,
                "steady_state_error": 0.01,
            },
            "stable": True,
            "requirements_met": requirements_met,
            "result": result,
        }
    )


class TestStudentInitialization:
    def test_init_creates_all_mec271_competencies_not_demonstrated(self):
        manager = StudentModelManager.create_new_student("stu-1")
        assert set(manager.profile.competencies.keys()) == set(MEC271_NODE_IDS)
        assert len(manager.profile.competencies) == 5
        for record in manager.profile.competencies.values():
            assert record.state == CompetencyState.NOT_DEMONSTRATED
            assert record.evidence_history == []

    def test_student_profile_defaults_to_mec271_course(self):
        manager = StudentModelManager.create_new_student("stu-1")
        assert manager.profile.student_id == "stu-1"
        assert manager.profile.course_id == "MEC271"

    def test_get_state_returns_not_demonstrated_initially(self):
        manager = StudentModelManager.create_new_student("stu-1")
        assert manager.get_state("MEC271-FB") == CompetencyState.NOT_DEMONSTRATED

    def test_get_state_raises_for_unknown_competency(self):
        manager = StudentModelManager.create_new_student("stu-1")
        with pytest.raises(KeyError):
            manager.get_state("UNKNOWN-COMPETENCY")


class TestTargetSelection:
    def test_initial_target_is_feedback_fundamentals(self):
        manager = StudentModelManager.create_new_student("stu-1")
        target = manager.get_next_target_competency()
        assert target is not None
        assert target.id == "MEC271-FB"

    def test_completing_feedback_unblocks_pid_fundamentals_as_target(self):
        manager = StudentModelManager.create_new_student("stu-1")
        manager.record_evidence("MEC271-FB", make_evidence(attempt=1))
        manager.record_evidence("MEC271-FB", make_evidence(attempt=2))

        assert manager.get_state("MEC271-FB") == CompetencyState.DEMONSTRATED
        assert manager.get_completed_competencies() == ["MEC271-FB"]
        unblocked = manager.get_unblocked_competencies()
        assert [node.id for node in unblocked] == ["MEC271-PID-FUND"]
        assert manager.get_next_target_competency().id == "MEC271-PID-FUND"

    def test_full_sequence_target_progression(self):
        manager = StudentModelManager.create_new_student("stu-1")
        for competency_id in MEC271_NODE_IDS[:-1]:
            manager.record_evidence(competency_id, make_evidence(attempt=1))
            manager.record_evidence(competency_id, make_evidence(attempt=2))
            assert manager.get_state(competency_id) == CompetencyState.DEMONSTRATED
        target = manager.get_next_target_competency()
        assert target.id == "MEC271-RESP-ANALYSIS"

    def test_no_target_when_all_competencies_demonstrated(self):
        manager = StudentModelManager.create_new_student("stu-1")
        for competency_id in MEC271_NODE_IDS:
            manager.record_evidence(competency_id, make_evidence(attempt=1))
            manager.record_evidence(competency_id, make_evidence(attempt=2))
        assert manager.get_completed_competencies() == MEC271_NODE_IDS
        assert manager.get_next_target_competency() is None
        assert manager.get_unblocked_competencies() == []


class TestStateTransitions:
    def test_passing_evidence_progresses_to_developing_then_demonstrated(self):
        manager = StudentModelManager.create_new_student("stu-1")

        state = manager.record_evidence("MEC271-FB", make_evidence(attempt=1))
        assert state == CompetencyState.DEVELOPING
        assert manager.get_state("MEC271-FB") == CompetencyState.DEVELOPING

        state = manager.record_evidence("MEC271-FB", make_evidence(attempt=2))
        assert state == CompetencyState.DEMONSTRATED
        assert manager.get_state("MEC271-FB") == CompetencyState.DEMONSTRATED

    def test_failing_evidence_keeps_state_not_demonstrated(self):
        manager = StudentModelManager.create_new_student("stu-1")
        state = manager.record_evidence(
            "MEC271-FB", make_evidence(attempt=1, requirements_met=False, result="FAIL")
        )
        assert state == CompetencyState.NOT_DEMONSTRATED
        assert manager.get_state("MEC271-FB") == CompetencyState.NOT_DEMONSTRATED

    def test_recording_evidence_appends_to_history(self):
        manager = StudentModelManager.create_new_student("stu-1")
        manager.record_evidence("MEC271-FB", make_evidence(attempt=1))
        manager.record_evidence("MEC271-FB", make_evidence(attempt=2))
        record = manager.profile.competencies["MEC271-FB"]
        assert len(record.evidence_history) == 2
        assert record.evidence_history[0].task_id == "PID-001"


class TestSummaryMetrics:
    def test_summary_reflects_mixed_progress(self):
        manager = StudentModelManager.create_new_student("stu-1")

        # MEC271-FB -> DEMONSTRATED (2 passes)
        manager.record_evidence("MEC271-FB", make_evidence(attempt=1))
        manager.record_evidence("MEC271-FB", make_evidence(attempt=2))
        # MEC271-PID-FUND -> DEVELOPING (1 pass)
        manager.record_evidence("MEC271-PID-FUND", make_evidence(attempt=1))

        summary = manager.get_summary()
        assert summary["total_competencies"] == 5
        assert summary["demonstrated_count"] == 1
        assert summary["developing_count"] == 1
        assert summary["not_demonstrated_count"] == 3
        assert summary["unblocked_ids"] == ["MEC271-PID-FUND"]
        assert summary["target_competency_id"] == "MEC271-PID-FUND"

    def test_summary_for_fresh_student(self):
        manager = StudentModelManager.create_new_student("stu-1")
        summary = manager.get_summary()
        assert summary == {
            "total_competencies": 5,
            "demonstrated_count": 0,
            "developing_count": 0,
            "not_demonstrated_count": 5,
            "unblocked_ids": ["MEC271-FB"],
            "target_competency_id": "MEC271-FB",
        }

    def test_summary_with_failing_evidence_only(self):
        manager = StudentModelManager.create_new_student("stu-1")
        manager.record_evidence(
            "MEC271-FB", make_evidence(attempt=1, requirements_met=False, result="FAIL")
        )
        summary = manager.get_summary()
        assert summary["demonstrated_count"] == 0
        assert summary["developing_count"] == 0
        assert summary["not_demonstrated_count"] == 5
        assert summary["target_competency_id"] == "MEC271-FB"