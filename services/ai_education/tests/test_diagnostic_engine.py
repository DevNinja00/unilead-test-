"""Tests for the diagnostic engine."""

import pytest
from pydantic import ValidationError

from ai_education.domain.diagnostic import (
    DiagnosticAssessment,
    DiagnosticEngine,
    DiagnosticItem,
    DiagnosticResponse,
    DiagnosticResult,
)
from ai_education.domain.enums import CompetencyState
from ai_education.domain.student import StudentModelManager

MEC271_COMPETENCIES = [
    "MEC271-FB",
    "MEC271-PID-FUND",
    "MEC271-PID-REASON",
    "MEC271-PID-TUNE",
    "MEC271-RESP-ANALYSIS",
]


def make_items() -> list[DiagnosticItem]:
    """One item per MEC271 competency."""
    return [
        DiagnosticItem(
            item_id=node_id,
            competency_id=node_id,
            question=f"{node_id} question",
            options=[f"option-{i}" for i in range(4)],
            correct_option_index=0,
        )
        for node_id in MEC271_COMPETENCIES
    ]


def response(item_id: str, selected: int) -> DiagnosticResponse:
    return DiagnosticResponse(item_id=item_id, selected_option_index=selected)


def full_pass_responses() -> list[DiagnosticResponse]:
    """Answer every item correctly (correct_option_index is 0)."""
    return [response(node_id, 0) for node_id in MEC271_COMPETENCIES]


class TestFullDiagnosticPass:
    def test_full_pass_demonstrates_all_and_sets_terminal_target(self) -> None:
        manager = StudentModelManager.create_new_student("student-1")
        engine = DiagnosticEngine()
        assessment = DiagnosticAssessment(
            student_id="student-1", responses=full_pass_responses()
        )

        result = engine.evaluate_diagnostic(
            "student-1", assessment, make_items(), manager
        )

        assert result.recommended_start_node_id == "MEC271-RESP-ANALYSIS"
        assert all(
            state == CompetencyState.DEMONSTRATED
            for state in result.assessed_states.values()
        )
        assert manager.get_next_target_competency() is None
        for node_id in MEC271_COMPETENCIES:
            assert manager.get_state(node_id) == CompetencyState.DEMONSTRATED

    def test_full_pass_returns_a_diagnostic_result(self) -> None:
        manager = StudentModelManager.create_new_student("student-1")
        engine = DiagnosticEngine()
        assessment = DiagnosticAssessment(
            student_id="student-1", responses=full_pass_responses()
        )

        result = engine.evaluate_diagnostic(
            "student-1", assessment, make_items(), manager
        )

        assert isinstance(result, DiagnosticResult)
        assert result.diagnostic_summary  # non-empty human-readable summary
        assert result.assessed_states == {
            node_id: CompetencyState.DEMONSTRATED
            for node_id in MEC271_COMPETENCIES
        }


class TestDiagnosticFailureAtPrerequisite:
    def test_failure_at_pid_fund_places_student_there(self) -> None:
        manager = StudentModelManager.create_new_student("student-2")
        engine = DiagnosticEngine()
        responses = [
            response("MEC271-FB", 0),            # correct
            response("MEC271-PID-FUND", 2),      # WRONG
            response("MEC271-PID-REASON", 0),    # correct
            response("MEC271-PID-TUNE", 0),      # correct (but blocked)
            response("MEC271-RESP-ANALYSIS", 0), # correct (but blocked)
        ]
        assessment = DiagnosticAssessment(student_id="student-2", responses=responses)

        result = engine.evaluate_diagnostic(
            "student-2", assessment, make_items(), manager
        )

        assert result.recommended_start_node_id == "MEC271-PID-FUND"
        assert manager.get_next_target_competency() is not None
        assert manager.get_next_target_competency().id == "MEC271-PID-FUND"
        assert manager.get_state("MEC271-FB") == CompetencyState.DEMONSTRATED
        assert manager.get_state("MEC271-PID-FUND") == CompetencyState.NOT_DEMONSTRATED

    def test_pid_tune_not_demonstrated_despite_correct_answers(self) -> None:
        """Higher nodes are clamped when a prerequisite is not demonstrated."""
        manager = StudentModelManager.create_new_student("student-3")
        engine = DiagnosticEngine()
        responses = [
            response("MEC271-FB", 0),
            response("MEC271-PID-FUND", 2),  # blocks everything after
            response("MEC271-PID-TUNE", 0),  # answered correctly
        ]
        assessment = DiagnosticAssessment(student_id="student-3", responses=responses)

        result = engine.evaluate_diagnostic(
            "student-3", assessment, make_items(), manager
        )

        assert result.assessed_states["MEC271-PID-TUNE"] == CompetencyState.NOT_DEMONSTRATED
        assert manager.get_state("MEC271-PID-TUNE") == CompetencyState.NOT_DEMONSTRATED

    def test_developing_state_also_clamped_by_prerequisite(self) -> None:
        """A partially-correct node is not demonstrated when its prereq fails."""
        manager = StudentModelManager.create_new_student("student-4")
        engine = DiagnosticEngine()
        items = (
            make_items()
            + [
                DiagnosticItem(
                    item_id="fb-extra",
                    competency_id="MEC271-FB",
                    question="FB extra",
                    options=["a", "b"],
                    correct_option_index=1,
                )
            ]
        )
        responses = [
            response("MEC271-FB", 0),          # correct
            response("fb-extra", 0),           # WRONG -> FB is DEVELOPING down-tree,
                                               # but MEC271-PID-FUND depends on FB
            response("MEC271-PID-FUND", 2),    # wrong
        ]
        assessment = DiagnosticAssessment(student_id="student-4", responses=responses)

        result = engine.evaluate_diagnostic(
            "student-4", assessment, items, manager
        )

        assert result.assessed_states["MEC271-FB"] == CompetencyState.DEVELOPING
        assert result.recommended_start_node_id == "MEC271-FB"


class TestEmptyDiagnostic:
    def test_empty_responses_default_to_me271_fb(self) -> None:
        manager = StudentModelManager.create_new_student("student-5")
        engine = DiagnosticEngine()
        assessment = DiagnosticAssessment(student_id="student-5", responses=[])

        result = engine.evaluate_diagnostic(
            "student-5", assessment, make_items(), manager
        )

        assert result.recommended_start_node_id == "MEC271-FB"
        assert manager.get_next_target_competency().id == "MEC271-FB"
        assert all(
            state == CompetencyState.NOT_DEMONSTRATED
            for state in result.assessed_states.values()
        )
        assert "MEC271-FB" in result.diagnostic_summary
        assert manager.get_state("MEC271-FB") == CompetencyState.NOT_DEMONSTRATED


class TestDiagnosticValidation:
    def test_correct_option_index_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DiagnosticItem(
                item_id="q1",
                competency_id="MEC271-FB",
                question="q",
                options=["a", "b"],
                correct_option_index=5,
            )

    def test_student_id_mismatch_rejected(self) -> None:
        manager = StudentModelManager.create_new_student("student-6")
        engine = DiagnosticEngine()
        assessment = DiagnosticAssessment(
            student_id="someone-else", responses=full_pass_responses()
        )

        with pytest.raises(ValueError, match="does not match"):
            engine.evaluate_diagnostic(
                "student-6", assessment, make_items(), manager
            )

    def test_response_for_unknown_item_rejected(self) -> None:
        manager = StudentModelManager.create_new_student("student-7")
        engine = DiagnosticEngine()
        assessment = DiagnosticAssessment(
            student_id="student-7",
            responses=[response("no-such-item", 0)],
        )

        with pytest.raises(ValueError, match="unknown item"):
            engine.evaluate_diagnostic(
                "student-7", assessment, make_items(), manager
            )

    def test_item_for_unknown_competency_rejected(self) -> None:
        manager = StudentModelManager.create_new_student("student-8")
        engine = DiagnosticEngine()
        items = make_items()
        items.append(
            DiagnosticItem(
                item_id="weird",
                competency_id="NOT-REAL",
                question="q",
                options=["a", "b"],
                correct_option_index=0,
            )
        )
        assessment = DiagnosticAssessment(student_id="student-8")
        with pytest.raises(ValueError, match="unknown competency"):
            engine.evaluate_diagnostic(
                "student-8", assessment, items, manager
            )