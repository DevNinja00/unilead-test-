"""AI/Education subsystem of the AI Competency Coach.

Domain models, evidence schemas, and (future) LLM orchestration for
competency tracking on the MEC271 course.
"""

from ai_education.coach.modes import (
    BaseModeHandler,
    HintHandler,
    LearnHandler,
    PracticeHandler,
    ReflectHandler,
    RemediateHandler,
    TransferHandler,
    build_handler_registry,
)
from ai_education.coach.orchestrator import (
    AICoachOrchestrator,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.domain.courses.mec271 import MEC271_NODE_IDS, build_mec271_graph
from ai_education.domain.diagnostic import (
    DiagnosticAssessment,
    DiagnosticEngine,
    DiagnosticItem,
    DiagnosticResponse,
    DiagnosticResult,
)
from ai_education.domain.enums import CoachMode, CompetencyState, EvidenceType
from ai_education.domain.evidence import (
    PIDParameters,
    PracticalEvidence,
    SimulationMetrics,
)
from ai_education.domain.graph import CompetencyGraph
from ai_education.domain.models import CompetencyNode, CompetencyRecord, StudentProfile
from ai_education.domain.student import StudentModelManager
from ai_education.fluency import (
    AIFluencyEngine,
    AIFluencyMetrics,
    AIFluencyReport,
    FluencyLevel,
    compute_prompt_specificity,
    extract_technical_signals,
    score_fluency_level,
)
from ai_education.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMStructureError,
)
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider
from ai_education.llm.ollama import OllamaProvider
from ai_education.llm.openai import OpenAIProvider
from ai_education.mastery import (
    MasteryDeterminationEngine,
    MasteryEvaluationResult,
    MasteryRuleConfig,
    check_evidence_consistency,
)
from ai_education.reasoning import (
    EvidenceReasoningEngine,
    EvidenceReasoningSummary,
    PIDMisconception,
    diagnose_misconception,
)
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
from ai_education.simulation import (
    DiscretePID,
    PIDSimulationEngine,
    SecondOrderPlant,
    StepMetrics,
    StepResponse,
)
from ai_education.strategy import (
    AdaptiveStrategyEngine,
    AdaptiveStrategyPlan,
    LearningPace,
    ScaffoldingLevel,
    evaluate_pace,
    evaluate_scaffolding_level,
)
from ai_education.api import (
    APIGateway,
    ChatRequest,
    ChatResponse,
    MetricEvidence,
    PIDGains,
    StudentProfileResponse,
    TelemetrySubmissionRequest,
    TelemetrySubmissionResponse,
    create_app,
)
from ai_education.fallbacks import (
    CoachResponse,
    FallbackEngine,
    get_demo_student_profiles,
    get_demo_telemetry_samples,
)
from ai_education.transfer import (
    TRANSFER_DOMAIN_TERMS,
    TransferAssessmentEngine,
    TransferEvaluationResult,
    TransferScenario,
    get_transfer_scenario,
    get_transfer_scenarios,
)

__all__ = [
    "AICoachOrchestrator",
    "APIGateway",
    "ChatRequest",
    "ChatResponse",
    "MetricEvidence",
    "PIDGains",
    "StudentProfileResponse",
    "TelemetrySubmissionRequest",
    "TelemetrySubmissionResponse",
    "create_app",
    "AdaptiveStrategyEngine",
    "AdaptiveStrategyPlan",
    "AIFluencyEngine",
    "AIFluencyMetrics",
    "AIFluencyReport",
    "BaseModeHandler",
    "CoachMode",
    "CoachResponse",
    "CoachTurnRequest",
    "CoachTurnResponse",
    "CompetencyGraph",
    "CompetencyNode",
    "CompetencyRecord",
    "CompetencyState",
    "DiagnosticAssessment",
    "DiagnosticEngine",
    "DiagnosticItem",
    "DiagnosticResponse",
    "DiagnosticResult",
    "DiscretePID",
    "EvidenceReasoningEngine",
    "EvidenceReasoningSummary",
    "EvidenceType",
    "FallbackEngine",
    "FluencyLevel",
    "HintHandler",
    "LLMConfig",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "LLMStructureError",
    "LearnHandler",
    "LearningPace",
    "MEC271_NODE_IDS",
    "MockLLMProvider",
    "MasteryDeterminationEngine",
    "MasteryEvaluationResult",
    "MasteryRuleConfig",
    "OllamaProvider",
    "OpenAIProvider",
    "PIDMisconception",
    "PIDParameters",
    "PIDSimulationEngine",
    "PracticeHandler",
    "PracticalEvidence",
    "ReflectHandler",
    "RemediateHandler",
    "RemediationAction",
    "RemediationEngine",
    "RemediationPlan",
    "RoboticsEvidenceIngestor",
    "ScaffoldingLevel",
    "SecondOrderPlant",
    "SimulationMetrics",
    "StepMetrics",
    "StepResponse",
    "StepResponseTelemetry",
    "StudentModelManager",
    "StudentProfile",
    "TelemetryThresholds",
    "TransferHandler",
    "TransferScenario",
    "TransferAssessmentEngine",
    "TransferEvaluationResult",
    "build_handler_registry",
    "build_mec271_graph",
    "diagnose_misconception",
    "evaluate_pace",
    "evaluate_scaffolding_level",
    "get_remediation_strategy",
    "check_evidence_consistency",
    "get_transfer_scenario",
    "get_transfer_scenarios",
    "get_demo_student_profiles",
    "get_demo_telemetry_samples",
    "compute_prompt_specificity",
    "extract_technical_signals",
    "score_fluency_level",
]

__version__ = "0.1.0"