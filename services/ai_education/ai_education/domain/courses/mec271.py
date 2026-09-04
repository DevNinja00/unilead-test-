"""Standard MEC271 course competency graph (PID tuning sequence).

Pedagogical sequence:

    MEC271-FB  (Feedback Fundamentals)
        -> MEC271-PID-FUND (PID Fundamentals)
            -> MEC271-PID-REASON (PID Parameter Reasoning)
                -> MEC271-PID-TUNE (PID Tuning & Optimization)
                    -> MEC271-RESP-ANALYSIS (Response & Transient Analysis)
"""

from typing import List

from ai_education.domain.graph import CompetencyGraph
from ai_education.domain.models import CompetencyNode

MEC271_NODE_IDS = [
    "MEC271-FB",
    "MEC271-PID-FUND",
    "MEC271-PID-REASON",
    "MEC271-PID-TUNE",
    "MEC271-RESP-ANALYSIS",
]


def _build_nodes() -> List[CompetencyNode]:
    return [
        CompetencyNode(
            id="MEC271-FB",
            title="Feedback Fundamentals",
            description=(
                "Closed-loop feedback concepts: reference vs. measured signal, "
                "error signal, and the role of the loop in regulation."
            ),
            parent_ids=[],
        ),
        CompetencyNode(
            id="MEC271-PID-FUND",
            title="PID Fundamentals",
            description=(
                "Proportional, integral, and derivative control actions, their "
                "roles, and how they combine in a PID controller."
            ),
            parent_ids=["MEC271-FB"],
        ),
        CompetencyNode(
            id="MEC271-PID-REASON",
            title="PID Parameter Reasoning",
            description=(
                "Reasoning about how gains affect behaviour: handling of "
                "overshoot, settling time, and steady-state error."
            ),
            parent_ids=["MEC271-PID-FUND"],
        ),
        CompetencyNode(
            id="MEC271-PID-TUNE",
            title="PID Tuning & Optimization",
            description=(
                "Practical tuning workflows (e.g. Ziegler-Nichols, trial-and-"
                "error) and optimization of gains in simulation."
            ),
            parent_ids=["MEC271-PID-REASON"],
        ),
        CompetencyNode(
            id="MEC271-RESP-ANALYSIS",
            title="Response & Transient Analysis",
            description=(
                "Interpreting closed-loop step responses: overshoot, settling "
                "time, steady-state error, and stability assessment."
            ),
            parent_ids=["MEC271-PID-TUNE"],
        ),
    ]


def build_mec271_graph() -> CompetencyGraph:
    """Build the standard MEC271 competency graph as a DAG."""
    graph = CompetencyGraph()
    for node in _build_nodes():
        graph.add_node(node)
    return graph