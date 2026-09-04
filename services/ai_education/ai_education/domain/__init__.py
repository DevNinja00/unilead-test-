"""Domain layer for the AI/Education subsystem.

Contains enums, evidence schemas, competency domain models, and the
competency graph structure. Pure Pydantic v2 models - no ORM or
database dependencies.
"""

from ai_education.domain.courses.mec271 import (
    MEC271_NODE_IDS,
    build_mec271_graph,
)
from ai_education.domain.diagnostic import (
    DiagnosticAssessment,
    DiagnosticEngine,
    DiagnosticItem,
    DiagnosticResponse,
    DiagnosticResult,
)
from ai_education.domain.graph import CompetencyGraph
from ai_education.domain.student import StudentModelManager

__all__ = [
    "CompetencyGraph",
    "DiagnosticAssessment",
    "DiagnosticEngine",
    "DiagnosticItem",
    "DiagnosticResponse",
    "DiagnosticResult",
    "MEC271_NODE_IDS",
    "StudentModelManager",
    "build_mec271_graph",
]