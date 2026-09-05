"""Boot smoke tests for the unified Unilead API.

Verifies the three things that ``apps/api/app/main.py`` promises:
  - importing the module yields a FastAPI app,
  - the Compass MVP routes are mounted under ``/api/*`` (now JWT-protected),
  - the AI Education routes are mounted under ``/api/ai-education/*``,
  - both halves answer their respective liveness probes with 200.

Because most Compass routes now require authentication, the tests sign up
a fresh demo user and use the returned JWT to call the protected routes.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app, build_provider, build_singletons


def test_app_is_a_fastapi_instance() -> None:
    assert isinstance(app, FastAPI)


def _signup_and_verify(client, email: str = "", password: str = "TestPass!123") -> tuple[str, str]:
    """Sign up a fresh user, complete email verification, return (token, email)."""
    import time

    from app.services import verification

    uniq = str(int(time.time()))
    if not email:
        email = f"boot-{uniq}@university.edu.eg"
    response = client.post(
        "/api/auth/signup",
        json={"name": "Boot Test", "username": f"boot{uniq}", "email": email, "password": password},
    )
    assert response.status_code == 201, f"signup failed: {response.text}"
    assert response.json()["verification_required"] is True

    code = verification.last_sent.get(email)
    assert code, f"no verification code recorded for {email}"
    response = client.post(
        "/api/auth/verify-email",
        json={"email": email, "code": code},
    )
    assert response.status_code == 200, f"verify-email failed: {response.text}"
    return response.json()["access_token"], email


def test_app_exposes_compass_routes() -> None:
    """``/api/competencies`` is JWT-protected — sign up, verify, then GET."""
    client = TestClient(app)
    token, _ = _signup_and_verify(client)
    response = client.get(
        "/api/competencies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"GET /api/competencies failed: {response.text}"
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    # Fresh user → all competencies start at not_started / 0%
    for c in body:
        assert c["status"] == "not_started", f"{c['name']} should start not_started"
        assert c["progress"] == 0, f"{c['name']} should start at 0%"


def test_compass_routes_reject_missing_token() -> None:
    """Without a JWT, ``/api/competencies`` should 401."""
    client = TestClient(app)
    response = client.get("/api/competencies")
    assert response.status_code == 401


def test_app_exposes_ai_education_routes() -> None:
    client = TestClient(app)
    response = client.get("/api/ai-education/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-education-gateway"}


def test_root_health_check_reports_both_modules() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "unilead-api"
    assert "compass" in body["modules"]
    assert "ai-education" in body["modules"]


def test_build_singletons_returns_all_four_dependencies() -> None:
    from ai_education import (
        AICoachOrchestrator,
        EvidenceReasoningEngine,
        StudentModelManager,
    )
    from ai_education.llm.base import LLMProvider

    from app.config import Settings

    settings = Settings(llm_provider_type="mock")
    manager, orchestrator, reasoning_engine, provider = build_singletons(settings)
    assert isinstance(manager, StudentModelManager)
    assert isinstance(orchestrator, AICoachOrchestrator)
    assert isinstance(reasoning_engine, EvidenceReasoningEngine)
    assert isinstance(provider, LLMProvider)


def test_environment_drives_provider_selection() -> None:
    from ai_education.llm.ollama import OllamaProvider

    from app.config import Settings

    settings = Settings(
        llm_provider_type="ollama",
        ollama_base_url="http://127.0.0.1:11434",
    )
    provider = build_provider(settings)
    assert isinstance(provider, OllamaProvider)
