"""Unit tests for the CompetencyGraph structure and the MEC271 graph."""

import pytest

from ai_education.domain.courses.mec271 import build_mec271_graph
from ai_education.domain.graph import CompetencyGraph
from ai_education.domain.models import CompetencyNode

MEC271_SEQUENCE = [
    "MEC271-FB",
    "MEC271-PID-FUND",
    "MEC271-PID-REASON",
    "MEC271-PID-TUNE",
    "MEC271-RESP-ANALYSIS",
]


class TestMEC271Structure:
    def test_standard_graph_contains_exact_nodes(self):
        graph = build_mec271_graph()
        assert len(graph) == 5
        for node_id in MEC271_SEQUENCE:
            node = graph.get_node(node_id)
            assert node is not None
            assert node.id == node_id

    def test_standard_graph_titles(self):
        graph = build_mec271_graph()
        assert graph.get_node("MEC271-FB").title == "Feedback Fundamentals"
        assert graph.get_node("MEC271-PID-FUND").title == "PID Fundamentals"
        assert graph.get_node("MEC271-PID-REASON").title == "PID Parameter Reasoning"
        assert (
            graph.get_node("MEC271-PID-TUNE").title
            == "PID Tuning & Optimization"
        )
        assert (
            graph.get_node("MEC271-RESP-ANALYSIS").title
            == "Response & Transient Analysis"
        )

    def test_standard_graph_prerequisite_edges(self):
        graph = build_mec271_graph()
        assert graph.get_node("MEC271-FB").parent_ids == []
        assert graph.get_node("MEC271-PID-FUND").parent_ids == ["MEC271-FB"]
        assert graph.get_node("MEC271-PID-REASON").parent_ids == [
            "MEC271-PID-FUND"
        ]
        assert graph.get_node("MEC271-PID-TUNE").parent_ids == [
            "MEC271-PID-REASON"
        ]
        assert graph.get_node("MEC271-RESP-ANALYSIS").parent_ids == [
            "MEC271-PID-TUNE"
        ]


class TestDAGValidation:
    def test_standard_mec271_graph_is_valid_dag(self):
        graph = build_mec271_graph()
        assert graph.validate_dag() is True

    def test_single_node_graph_is_valid_dag(self):
        graph = CompetencyGraph()
        graph.add_node(CompetencyNode(id="A", title="Only node"))
        assert graph.validate_dag() is True

    def test_detects_two_node_cycle(self):
        graph = CompetencyGraph()
        graph.add_node(
            CompetencyNode(id="A", title="A", parent_ids=["B"])
        )
        graph.add_node(
            CompetencyNode(id="B", title="B", parent_ids=["A"])
        )
        assert graph.validate_dag() is False

    def test_detects_self_cycle(self):
        graph = CompetencyGraph()
        graph.add_node(
            CompetencyNode(id="A", title="A", parent_ids=["A"])
        )
        assert graph.validate_dag() is False

    def test_detects_cycle_embedded_in_larger_graph(self):
        graph = CompetencyGraph()
        graph.add_node(CompetencyNode(id="A", title="A"))
        graph.add_node(CompetencyNode(id="B", title="B", parent_ids=["A", "C"]))
        graph.add_node(CompetencyNode(id="C", title="C", parent_ids=["B"]))
        assert graph.validate_dag() is False

    def test_dangling_prerequisite_is_not_valid_dag(self):
        graph = CompetencyGraph()
        graph.add_node(
            CompetencyNode(id="A", title="A", parent_ids=["GHOST"])
        )
        assert graph.validate_dag() is False


class TestPrerequisiteResolution:
    def test_get_node_returns_none_for_unknown(self):
        graph = build_mec271_graph()
        assert graph.get_node("DOES-NOT-EXIST") is None

    def test_direct_prerequisites(self):
        graph = build_mec271_graph()
        prereqs = graph.get_prerequisites("MEC271-PID-TUNE")
        assert [n.id for n in prereqs] == ["MEC271-PID-REASON"]

    def test_all_ancestors_recursive_back_to_feedback_fundamentals(self):
        graph = build_mec271_graph()
        ancestors = graph.get_all_ancestors("MEC271-PID-TUNE")
        ancestor_ids = [n.id for n in ancestors]
        # Full prerequisite chain back to the root node.
        assert ancestor_ids == [
            "MEC271-PID-REASON",
            "MEC271-PID-FUND",
            "MEC271-FB",
        ]
        assert "MEC271-FB" in ancestor_ids

    def test_all_ancestors_of_root_is_empty(self):
        graph = build_mec271_graph()
        assert graph.get_all_ancestors("MEC271-FB") == []

    def test_get_prerequisites_raises_for_unknown_node(self):
        graph = build_mec271_graph()
        with pytest.raises(KeyError):
            graph.get_prerequisites("GHOST")


class TestUnblockedNodes:
    def test_no_competencies_completed_unblocks_only_root(self):
        graph = build_mec271_graph()
        unblocked = graph.get_unblocked_nodes(set())
        assert [n.id for n in unblocked] == ["MEC271-FB"]

    def test_completing_feedbacks_unblocks_pid_fundamentals(self):
        graph = build_mec271_graph()
        unblocked = graph.get_unblocked_nodes({"MEC271-FB"})
        assert [n.id for n in unblocked] == ["MEC271-PID-FUND"]

    def test_chained_unblocking(self):
        graph = build_mec271_graph()
        completed = {"MEC271-FB", "MEC271-PID-FUND"}
        unblocked = graph.get_unblocked_nodes(completed)
        assert [n.id for n in unblocked] == ["MEC271-PID-REASON"]

    def test_everything_almost_completed(self):
        graph = build_mec271_graph()
        completed = set(MEC271_SEQUENCE[:-1])
        unblocked = graph.get_unblocked_nodes(completed)
        assert [n.id for n in unblocked] == ["MEC271-RESP-ANALYSIS"]

    def test_fully_completed_graph_unblocks_nothing(self):
        graph = build_mec271_graph()
        assert graph.get_unblocked_nodes(set(MEC271_SEQUENCE)) == []

    def test_completed_unrelated_ids_unblocks_only_root(self):
        graph = build_mec271_graph()
        unblocked = graph.get_unblocked_nodes({"UNRELATED-999"})
        assert [n.id for n in unblocked] == ["MEC271-FB"]


class TestGraphSanity:
    def test_duplicate_add_rejected(self):
        graph = CompetencyGraph()
        graph.add_node(CompetencyNode(id="A", title="A"))
        with pytest.raises(ValueError):
            graph.add_node(CompetencyNode(id="A", title="Duplicate"))

    def test_membership(self):
        graph = build_mec271_graph()
        assert "MEC271-FB" in graph
        assert "GHOST" not in graph

    def test_sequential_completion_reaches_full_sequence(self):
        graph = build_mec271_graph()
        completed: set[str] = set()
        for expected in MEC271_SEQUENCE:
            unblocked = graph.get_unblocked_nodes(completed)
            assert [n.id for n in unblocked] == [expected]
            completed.add(expected)