"""FastAPI application factory for the AI/Education gateway.

``create_app`` wires the three platform singletons (student model manager,
AI Coach orchestrator, and evidence reasoning engine) into ``app.state`` so
the router relies on a stable, persisted backend across requests. Tests
inject their own fakes via ``create_app(...)``; the module-level ``app`` is
a convenience for local serving and TestClient smoke checks.
"""

from typing import Optional

from fastapi import FastAPI

from ai_education.api.router import APIGateway, build_router
from ai_education.coach.orchestrator import AICoachOrchestrator
from ai_education.domain.student import StudentModelManager
from ai_education.llm.base import LLMProvider
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider
from ai_education.reasoning import EvidenceReasoningEngine

__all__ = ["create_app", "app"]

DEFAULT_STUDENT_ID = "api-gateway-student"
DEFAULT_COURSE_ID = "MEC271"


def create_app(
    student_manager: Optional[StudentModelManager] = None,
    llm_provider: Optional[LLMProvider] = None,
    reasoning_engine: Optional[EvidenceReasoningEngine] = None,
) -> FastAPI:
    """Build a gateway app, falling back to deterministic defaults."""
    manager = student_manager or StudentModelManager.create_new_student(
        DEFAULT_STUDENT_ID, course_id=DEFAULT_COURSE_ID
    )
    provider = llm_provider or MockLLMProvider(
        LLMConfig(provider_type="mock", model_name="api-gateway")
    )
    orchestrator = AICoachOrchestrator(
        student_manager=manager, llm_provider=provider
    )
    engine = reasoning_engine or EvidenceReasoningEngine()
    gateway = APIGateway(
        student_manager=manager,
        orchestrator=orchestrator,
        reasoning_engine=engine,
    )
    application = FastAPI(
        title="AI Education Gateway",
        description="HTTP gateway over the AI Education platform.",
        version="0.1.0",
    )
    application.state.gateway = gateway
    application.include_router(build_router(gateway))
    return application


app = create_app()