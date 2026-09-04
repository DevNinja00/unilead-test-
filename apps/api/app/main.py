"""Unified FastAPI entrypoint for the Unilead platform.

This single app serves both:
  - The Compass MVP API (competencies, progress, diagnostic, learning,
    practice, coach, review, simulation, onboarding, **remediation,
    transfer**) — original Platform backend routes under ``/api/*``.
  - The AI Education gateway (coach chat, evidence telemetry, simulate,
    student profile) — under ``/api/ai-education/*``.

The two halves share the same FastAPI instance, CORS middleware, and
configuration. The AI Education half is wired from the ai_education
library at ``services/ai_education/`` (imported via the path bootstrap
in ``app.config``).

The Compass services (``coach_service``, ``simulation_service``,
``diagnostic_service``) are wired to the same AI Education singletons
via the ``ai_education_bridge`` module — so a coach turn or a simulation
run on ``/api/coach`` or ``/api/simulation`` updates the same student
model that ``/api/ai-education/coach/chat`` would.
"""

from __future__ import annotations

from pathlib import Path

# AI Education gateway wiring
from ai_education import (
    AICoachOrchestrator,
    EvidenceReasoningEngine,
    StudentModelManager,
)
from ai_education.api.router import APIGateway, build_router
from ai_education.llm import MockLLMProvider, OllamaProvider, OpenAIProvider
from ai_education.llm.base import LLMProvider
from ai_education.llm.config import LLMConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# config import bootstraps sys.path so ai_education is importable
from .config import Settings, get_cors_origins

# Original Platform/backend routers + new remediation, transfer, instructor,
# evidence, and auth routers
from .routers import (
    auth,
    coach,
    competencies,
    diagnostic,
    evidence,
    instructor,
    learning,
    onboarding,
    practice,
    progress,
    remediation,
    review,
    simulation,
    transfer,
)

__all__ = ["app", "build_provider", "build_singletons"]


DEFAULT_MODEL_NAMES = {
    "mock": "api-gateway",
    "ollama": "llama3.2",
    "openai": "gpt-4o-mini",
}


def build_provider(settings: Settings) -> LLMProvider:
    """Construct the configured LLM provider, falling back to ``mock``."""
    config = LLMConfig(
        provider_type=settings.llm_provider_type,
        model_name=settings.llm_model or DEFAULT_MODEL_NAMES[settings.llm_provider_type],
        base_url=(
            settings.ollama_base_url
            if settings.llm_provider_type == "ollama"
            else settings.openai_base_url
        ),
        api_key=settings.openai_api_key,
    )
    if settings.llm_provider_type == "ollama":
        return OllamaProvider(config)
    if settings.llm_provider_type == "openai":
        return OpenAIProvider(config)
    return MockLLMProvider(config)


def build_singletons(
    settings: Settings,
) -> tuple[StudentModelManager, AICoachOrchestrator, EvidenceReasoningEngine, LLMProvider]:
    """Create the three gateway singletons plus the provider they share."""
    manager = StudentModelManager.create_new_student(
        settings.student_id, course_id=settings.course_id
    )
    provider = build_provider(settings)
    orchestrator = AICoachOrchestrator(student_manager=manager, llm_provider=provider)
    reasoning_engine = EvidenceReasoningEngine()
    return manager, orchestrator, reasoning_engine, provider


# --- Application bootstrap --------------------------------------------------

settings = Settings()
manager, orchestrator, reasoning_engine, provider = build_singletons(settings)

app = FastAPI(
    title="Unilead API",
    description=(
        "Unified gateway for the Unilead platform. Serves both the Compass "
        "MVP API (competencies, progress, diagnostic, learning, practice, "
        "coach, review, simulation, onboarding, remediation, transfer) and "
        "the AI Education gateway (coach chat, evidence telemetry, student "
        "profile). The Compass services are wired to the same AI Education "
        "singletons so every endpoint shares one student model. All state "
        "is persisted to SQLite via SQLAlchemy — see the db/ package."
    ),
    version="0.3.0",
    docs_url=None if settings.env == "production" else "/docs",
    redoc_url=None if settings.env == "production" else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# --- Security headers middleware -------------------------------------------
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    return response


# --- Database: create tables on startup (no demo seeds) ---------------
from .db import create_all_tables, seed_default_students_if_empty  # noqa: E402

create_all_tables()
seed_default_students_if_empty()  # no-op now — every student is created on signup

# --- Per-user AI Education manager pool + shared LLM provider -----------
# The gateway is no longer a singleton — each request resolves its own
# gateway from the current user's student_id (see services.manager_pool).
# We only keep the LLM provider + settings on app.state because they're
# global; student-specific state lives in the per-user pool.
app.state.llm_provider = provider
app.state.ai_education_llm_provider = provider  # alias used by manager_pool.py
app.state.llm_settings = settings

# --- Compass MVP routes (under /api/*) --------------------------------------
app.include_router(onboarding.router)
app.include_router(diagnostic.router)
app.include_router(learning.router)
app.include_router(practice.router)
app.include_router(coach.router)
app.include_router(progress.router)
app.include_router(competencies.router)
app.include_router(simulation.router)
app.include_router(review.router)
# New: remediation + transfer + instructor + evidence — wired to the
# AI Education engines and the multi-student registry.
app.include_router(remediation.router)
app.include_router(transfer.router)
app.include_router(instructor.router)
app.include_router(evidence.router)
# Auth (signup/login/me) — wired to the DB.
app.include_router(auth.router)

# The legacy AI Education gateway routes (/api/ai-education/*) are still
# available as a back-compat layer — they construct a per-request gateway
# from the default student_id. The Compass routes (above) are the primary
# entry points used by the frontend and now read student_id from the JWT.

# Build a default student_manager so the legacy routes still work for tests
# that don't have a JWT (e.g. ai_education's own tests). This gateway
# shares state with the per-user pool only if you also push it in.
_default_manager = StudentModelManager.create_new_student(
    settings.student_id, course_id=settings.course_id
)
_default_gateway = APIGateway(
    student_manager=_default_manager,
    orchestrator=AICoachOrchestrator(student_manager=_default_manager, llm_provider=provider),
    reasoning_engine=reasoning_engine,
)
app.state.ai_education_gateway = _default_gateway
app.include_router(
    build_router(_default_gateway),
    prefix="/api/ai-education",
    tags=["ai-education"],
)


# --- Startup assertion: JWT secret must be changed from default -----------
_DEFAULT_JWT_SECRETS = {
    "change-me-in-production-please-use-a-long-random-string",
    "dev-secret-change-me",
}
if settings.jwt_secret in _DEFAULT_JWT_SECRETS:
    import logging

    _log = logging.getLogger("unilead.main")
    if settings.enforce_jwt_secret:
        _log.critical(
            "JWT_SECRET is using a default value. Set JWT_SECRET env var to a "
            "strong random string and set ENFORCE_JWT_SECRET=true."
        )
        raise SystemExit(
            "Refusing to start with default JWT secret. Set JWT_SECRET to a strong random value."
        )
    _log.warning(
        "JWT_SECRET is using a default value — set JWT_SECRET env var to a "
        "strong random string in production!"
    )


@app.get("/", tags=["health"])
def health_check() -> dict:
    """Top-level liveness probe."""
    return {
        "status": "ok",
        "service": "unilead-api",
        "modules": ["compass", "ai-education"],
    }


@app.get("/healthz", tags=["health"])
def healthz() -> dict:
    """Kubernetes-style liveness probe."""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readyz() -> dict:
    """Readiness probe — verifies DB connectivity."""
    from sqlalchemy import text

    from .db import SessionLocal

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        return {"status": "not_ready", "database": str(exc)}


def main() -> None:
    """Run the server with uvicorn (reloads on source changes)."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        app_dir=str(Path(__file__).resolve().parent.parent),
        log_level="info",
    )


if __name__ == "__main__":
    main()
