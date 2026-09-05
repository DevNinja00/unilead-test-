"""
Quick smoke test for every endpoint. Uses a single shared user to avoid
triggering the signup rate limiter (3/hour/IP).

Run with: python -m pytest tests/test_smoke.py -v   (from the apps/api folder)
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import verification


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _signup(client, uniq: str, name: str = "Smoke Test") -> dict:
    """Sign up a user and return the JSON body (verification_required)."""
    r = client.post(
        "/api/auth/signup",
        json={
            "name": name,
            "username": uniq,
            "email": f"{uniq}@smoketest.edu.eg",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201, f"signup failed: {r.text}"
    return r.json()


def _verify(client, email: str) -> str:
    """Complete email verification and return the JWT."""
    code = verification.last_sent.get(email)
    assert code, f"no verification code recorded for {email}"
    r = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 200, f"verify-email failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(client):
    """Create one verified user for the entire test module and return auth headers."""
    uniq = "smoke" + str(int(time.time()))
    body = _signup(client, uniq)
    token = _verify(client, body["email"])
    return {"Authorization": f"Bearer {token}"}


def test_health_check(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_signup_requires_verification(client):
    uniq = "signup" + str(int(time.time()))
    body = _signup(client, uniq)
    assert body["verification_required"] is True
    assert "access_token" not in body


def test_verify_email_returns_token_and_me_works(client):
    uniq = "verify" + str(int(time.time()))
    body = _signup(client, uniq)
    token = _verify(client, body["email"])
    assert token

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == body["email"]


def test_login_correct_and_wrong(client):
    uniq = "login" + str(int(time.time()))
    email = f"{uniq}@smoketest.edu.eg"
    password = "Str0ng!Pass#word"
    _signup(client, uniq, name="Login Test")

    # not yet verified -> 403, even with correct password
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 403
    assert "not verified" in r.json()["detail"].lower()

    # bad password -> 401 even after verification
    _verify(client, email)
    r = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1!"})
    assert r.status_code == 401

    # correct login -> 200
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_me(client, auth_headers):
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert "email" in r.json()
    assert "student_id" in r.json()


def test_onboarding(client, auth_headers):
    r = client.post(
        "/api/onboarding",
        headers=auth_headers,
        json={
            "learning_challenge": "a",
            "preferred_method": "b",
            "obstacle": "c",
            "goal": "d",
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_diagnostic_questions(client, auth_headers):
    r = client.get("/api/diagnostic/questions", headers=auth_headers)
    assert r.status_code == 200
    questions = r.json()
    assert len(questions) == 5


def test_diagnostic_unauth(client):
    r = client.get("/api/diagnostic/questions")
    assert r.status_code == 401


def test_diagnostic_submit(client, auth_headers):
    r = client.get("/api/diagnostic/questions", headers=auth_headers)
    questions = r.json()
    r = client.post(
        "/api/diagnostic",
        headers=auth_headers,
        json={"answers": [{"question_id": q["id"], "option_id": "a"} for q in questions]},
    )
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_learning(client, auth_headers):
    r = client.get("/api/learning/pid-reasoning", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_learning_unauth(client):
    r = client.get("/api/learning/pid-reasoning")
    assert r.status_code == 401


def test_practice(client, auth_headers):
    r = client.get("/api/practice/pid-reasoning", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == "pid-001"


def test_practice_unauth(client):
    r = client.get("/api/practice/pid-reasoning")
    assert r.status_code == 401


def test_coach(client, auth_headers):
    r = client.post("/api/coach", headers=auth_headers, json={"message": "hello", "mode": "LEARN"})
    assert r.status_code == 200
    assert r.json()["message"]


def test_simulation(client, auth_headers):
    r = client.post(
        "/api/simulation",
        headers=auth_headers,
        json={
            "task_id": "pid-001",
            "competency_id": "pid-tuning",
            "kp": 1.0,
            "ki": 0.1,
            "kd": 0.05,
        },
    )
    assert r.status_code == 200
    assert "stable" in r.json()


def test_competencies(client, auth_headers):
    r = client.get("/api/competencies", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_progress(client, auth_headers):
    r = client.get("/api/progress", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["overall_progress"] is not None


def test_review_view(client, auth_headers):
    r = client.post(
        "/api/review",
        headers=auth_headers,
        json={"competency_id": "pid-reasoning", "finalize": False},
    )
    assert r.status_code == 200
    assert r.json()["progress"] is not None


def test_review_finalize(client, auth_headers):
    r = client.post(
        "/api/review",
        headers=auth_headers,
        json={"competency_id": "pid-reasoning", "finalize": True},
    )
    assert r.status_code == 200
    assert r.json()["competency_id"] == "pid-reasoning"


def test_evidence_timeline_me(client, auth_headers):
    r = client.get("/api/evidence/me/timeline", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_evidence_timeline_unauth(client):
    r = client.get("/api/evidence/me/timeline")
    assert r.status_code == 401


def test_instructor_forbidden_for_student(client, auth_headers):
    r = client.get("/api/instructor/summary", headers=auth_headers)
    assert r.status_code == 403
    r = client.get("/api/instructor/aggregate", headers=auth_headers)
    assert r.status_code == 403
    r = client.get("/api/instructor/students", headers=auth_headers)
    assert r.status_code == 403


def test_instructor_unauth(client):
    r = client.get("/api/instructor/students")
    assert r.status_code == 401
