"""Diagnostic engine: baseline assessment, start-node placement, state init.

Evaluates a learner's diagnostic responses against a course's competency
graph, enforces the prerequisite safety rule, and writes the resulting
baseline states back onto the student's competency records.
"""

from typing import Dict, List

from pydantic import BaseModel, Field, model_validator

from ai_education.domain.enums import CompetencyState
from ai_education.domain.graph import CompetencyGraph
from ai_education.domain.student import StudentModelManager


class DiagnosticItem(BaseModel):
    """A single question mapped to the competency it probes."""

    item_id: str
    competency_id: str
    question: str
    options: List[str] = Field(min_length=2)
    correct_option_index: int

    @model_validator(mode="after")
    def _validate_correct_option_index(self) -> "DiagnosticItem":
        if not 0 <= self.correct_option_index < len(self.options):
            raise ValueError(
                f"correct_option_index {self.correct_option_index} is out of "
                f"range for {len(self.options)} options"
            )
        return self


class DiagnosticResponse(BaseModel):
    """A learner's answer to one diagnostic item."""

    item_id: str
    selected_option_index: int = Field(ge=0)


class DiagnosticAssessment(BaseModel):
    """A completed diagnostic submission for a student."""

    student_id: str
    responses: List[DiagnosticResponse] = Field(default_factory=list)


class DiagnosticResult(BaseModel):
    """Output of a diagnostic evaluation: placement + assessed baseline state."""

    recommended_start_node_id: str
    assessed_states: Dict[str, CompetencyState]
    diagnostic_summary: str


class DiagnosticEngine:
    """Assesses baseline knowledge and determines start-node placement."""

    def evaluate_diagnostic(
        self,
        student_id: str,
        assessment: DiagnosticAssessment,
        items: List[DiagnosticItem],
        manager: StudentModelManager,
    ) -> DiagnosticResult:
        """Evaluate an assessment, update the manager, and return placement.

        Semantics:
        - Items whose answers are ALL correct mark their competency
          ``DEMONSTRATED``; partially correct marks ``DEVELOPING``; none
          correct (or unanswered) leaves ``NOT_DEMONSTRATED``.
        - Prerequisite Safety Rule: a node is never considered demonstrated
          while any prerequisite is not ``DEMONSTRATED`` (enforced in
          topological order).
        - The recommended start node is the earliest node in topological
          order that is not ``DEMONSTRATED``.
        """
        if assessment.student_id != student_id:
            raise ValueError(
                f"Assessment student_id {assessment.student_id!r} does not "
                f"match {student_id!r}"
            )

        item_by_id: Dict[str, DiagnosticItem] = {}
        for item in items:
            if item.item_id in item_by_id:
                raise ValueError(f"Duplicate diagnostic item id {item.item_id!r}")
            if item.competency_id not in manager.graph:
                raise ValueError(
                    f"Item {item.item_id!r} references unknown competency "
                    f"{item.competency_id!r}"
                )
            item_by_id[item.item_id] = item

        for response in assessment.responses:
            if response.item_id not in item_by_id:
                raise ValueError(
                    f"Response references unknown item {response.item_id!r}"
                )

        scores: Dict[str, List[bool]] = {
            node.id: [] for node in manager.graph.nodes
        }
        for response in assessment.responses:
            item = item_by_id[response.item_id]
            correct = response.selected_option_index == item.correct_option_index
            scores[item.competency_id].append(correct)

        raw: Dict[str, CompetencyState] = {}
        for node in manager.graph.nodes:
            results = scores[node.id]
            if not results or not any(results):
                raw[node.id] = CompetencyState.NOT_DEMONSTRATED
            elif all(results):
                raw[node.id] = CompetencyState.DEMONSTRATED
            else:
                raw[node.id] = CompetencyState.DEVELOPING

        topo_order = self._topological_order(manager.graph)

        final: Dict[str, CompetencyState] = {}
        for node_id in topo_order:
            node = manager.graph.get_node(node_id)
            if not node:
                raise KeyError(f"Unknown competency node id: {node_id!r}")
            prerequisites_ok = all(
                final[parent_id] == CompetencyState.DEMONSTRATED
                for parent_id in node.parent_ids
            )
            if not prerequisites_ok:
                final[node_id] = CompetencyState.NOT_DEMONSTRATED
            else:
                final[node_id] = raw[node_id]

        for node_id, state in final.items():
            manager.profile.competencies[node_id].state = state

        start_node_id = self._recommended_start_node_id(topo_order, final)
        summary = self._build_summary(start_node_id, final, manager.graph)

        return DiagnosticResult(
            recommended_start_node_id=start_node_id,
            assessed_states=final,
            diagnostic_summary=summary,
        )

    @staticmethod
    def _topological_order(graph: CompetencyGraph) -> List[str]:
        """Return node ids in deterministic topological order."""
        insertion_index = {
            node.id: idx for idx, node in enumerate(graph.nodes)
        }
        in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        children: Dict[str, List[str]] = {node.id: [] for node in graph.nodes}
        for node in graph.nodes:
            in_degree[node.id] = len(node.parent_ids)
            for parent_id in node.parent_ids:
                children[parent_id].append(node.id)

        ready = sorted(
            (nid for nid, deg in in_degree.items() if deg == 0),
            key=lambda nid: insertion_index[nid],
        )
        order: List[str] = []
        while ready:
            current = ready.pop(0)  # pops in insertion (deterministic) order
            order.append(current)
            for child_id in children[current]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    ready.append(child_id)
                    ready.sort(key=lambda nid: insertion_index[nid])

        if len(order) != len(graph.nodes):
            raise ValueError("Competency graph contains a cycle")
        return order

    @staticmethod
    def _recommended_start_node_id(
        topo_order: List[str],
        final_states: Dict[str, CompetencyState],
    ) -> str:
        """Earliest topological node not yet DEMONSTRATED.

        When every competency is demonstrated, the terminal (last) node in
        topological order is returned so the field stays meaningful.
        """
        for node_id in topo_order:
            if final_states[node_id] != CompetencyState.DEMONSTRATED:
                return node_id
        return topo_order[-1]

    @staticmethod
    def _build_summary(
        start_node_id: str,
        final_states: Dict[str, CompetencyState],
        graph: CompetencyGraph,
    ) -> str:
        demonstrated = sum(
            1 for state in final_states.values()
            if state == CompetencyState.DEMONSTRATED
        )
        node = graph.get_node(start_node_id)
        title = node.title if node else start_node_id
        return (
            f"Baseline assessment complete: {demonstrated} of "
            f"{len(final_states)} competencies demonstrated. Recommended "
            f"start: {start_node_id} ({title})."
        )