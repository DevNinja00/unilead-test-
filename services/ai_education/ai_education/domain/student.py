"""Student model manager: state transitions, progress queries, focus targeting.

Encapsulates a learner's competency state in front of a ``CompetencyGraph``.
All persistence decisions are left to higher layers - this module is pure
in-memory domain logic (no ORM / database dependencies).
"""

from typing import Dict, List, Optional, Set

from ai_education.domain.courses.mec271 import build_mec271_graph
from ai_education.domain.enums import CompetencyState
from ai_education.domain.evidence import PracticalEvidence
from ai_education.domain.graph import CompetencyGraph
from ai_education.domain.models import CompetencyNode, CompetencyRecord, StudentProfile


class StudentModelManager:
    """Owns a ``StudentProfile`` and drives competency state transitions."""

    def __init__(self, profile: StudentProfile, graph: CompetencyGraph) -> None:
        self.profile: StudentProfile = profile
        self.graph: CompetencyGraph = graph
        # Invariant: every node in the graph has a competency record, even if
        # the caller supplied a partial profile.
        self._ensure_all_competency_records()

    @classmethod
    def create_new_student(
        cls, student_id: str, course_id: str = "MEC271"
    ) -> "StudentModelManager":
        """Create a fresh learner with all course competencies at NOT_DEMONSTRATED."""
        graph = build_mec271_graph()
        competencies: Dict[str, CompetencyRecord] = {
            node.id: CompetencyRecord(
                competency_id=node.id,
                state=CompetencyState.NOT_DEMONSTRATED,
            )
            for node in graph.nodes
        }
        profile = StudentProfile(
            student_id=student_id,
            course_id=course_id,
            competencies=competencies,
        )
        return cls(profile=profile, graph=graph)

    def _ensure_all_competency_records(self) -> None:
        for node in self.graph.nodes:
            if node.id not in self.profile.competencies:
                self.profile.competencies[node.id] = CompetencyRecord(
                    competency_id=node.id
                )

    def _require_record(self, competency_id: str) -> CompetencyRecord:
        record = self.profile.competencies.get(competency_id)
        if record is None:
            raise KeyError(f"No competency record for {competency_id!r}")
        return record

    def get_state(self, competency_id: str) -> CompetencyState:
        """Return the current ``CompetencyState`` for a competency."""
        return self._require_record(competency_id).state

    def record_evidence(
        self, competency_id: str, evidence: PracticalEvidence
    ) -> CompetencyState:
        """Attach evidence to a competency record and return the new state.

        State progression follows ``CompetencyRecord.record_evidence``:
        no passing attempts -> NOT_DEMONSTRATED, one passing attempt ->
        DEVELOPING, two or more passing attempts -> DEMONSTRATED.
        """
        return self._require_record(competency_id).record_evidence(evidence)

    def get_completed_competencies(self) -> List[str]:
        """Return competency IDs whose state is DEMONSTRATED or MASTERED."""
        return [
            competency_id
            for competency_id, record in self.profile.competencies.items()
            if record.state
            in (CompetencyState.DEMONSTRATED, CompetencyState.MASTERED)
        ]

    def get_unblocked_competencies(self) -> List[CompetencyNode]:
        """Return uncompleted nodes whose prerequisites are all DEMONSTRATED."""
        completed: Set[str] = set(self.get_completed_competencies())
        return self.graph.get_unblocked_nodes(completed)

    def get_next_target_competency(self) -> Optional[CompetencyNode]:
        """Return the highest-priority unblocked competency for learning.

        Priority follows the graph's insertion order (the pedagogical
        sequence): the first available unblocked node is the next target.
        """
        unblocked = self.get_unblocked_competencies()
        return unblocked[0] if unblocked else None

    def get_summary(self) -> Dict[str, object]:
        """Return a structured breakdown of the learner's progress."""
        states = [record.state for record in self.profile.competencies.values()]
        target = self.get_next_target_competency()
        demonstrated = states.count(CompetencyState.DEMONSTRATED) + states.count(
            CompetencyState.MASTERED
        )
        return {
            "total_competencies": len(states),
            "demonstrated_count": demonstrated,
            "developing_count": states.count(CompetencyState.DEVELOPING),
            "not_demonstrated_count": states.count(CompetencyState.NOT_DEMONSTRATED),
            "unblocked_ids": [node.id for node in self.get_unblocked_competencies()],
            "target_competency_id": target.id if target else None,
        }