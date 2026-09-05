"""Tests for the security audit trail.

Verifies that security-relevant events (failed logins, successful logins,
verification, password resets) are recorded in the ``audit_logs`` table.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, models
from app.main import app
from app.services import verification


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _signup(client: TestClient, prefix: str) -> str:
    t = int(time.time())
    email = f"{prefix}{t}@university.edu.eg"
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "Audit Flow Test",
            "username": f"{prefix}{t}",
            "email": email,
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201, f"signup failed: {r.text}"
    return email


def _audit_rows(action: str, outcome: str | None = None) -> list[models.AuditLog]:
    with SessionLocal() as db:
        rows = db.query(models.AuditLog).filter(models.AuditLog.action == action).all()
        if outcome is not None:
            rows = [r for r in rows if r.outcome == outcome]
        return rows


def test_signup_records_audit_row(client):
    _signup(client, "audsg_")
    rows = _audit_rows("signup")
    assert rows, "expected at least one signup audit row"
    latest = rows[-1]
    assert latest.actor_role == "student"
    assert latest.outcome == "OK"


def test_failed_login_records_audit_row(client):
    email = _signup(client, "audfl_")
    r = client.post("/api/auth/login", json={"email": email, "password": "Wrong!Pass1"})
    assert r.status_code == 401
    rows = _audit_rows("login", "FAILED")
    assert rows, "expected a FAILED login audit row for the wrong password"


def test_successful_login_records_audit_row(client):
    email = _signup(client, "audok_")
    code = verification.last_sent.get(email)
    assert code
    assert (
        client.post("/api/auth/verify-email", json={"email": email, "code": code}).status_code
        == 200
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Pass#word"})
    assert r.status_code == 200
    rows = _audit_rows("login", "OK")
    assert rows, "expected an OK login audit row"


def test_verify_email_records_audit_row(client):
    email = _signup(client, "audvr_")
    code = verification.last_sent.get(email)
    assert code
    r = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 200
    rows = _audit_rows("verify_email", "OK")
    assert rows, "expected a verify_email audit row"


def test_password_reset_records_audit_row(client):
    email = _signup(client, "audpr_")
    code = verification.last_sent.get(email)
    assert code
    assert (
        client.post("/api/auth/verify-email", json={"email": email, "code": code}).status_code
        == 200
    )

    client.post("/api/auth/forgot-password", json={"email": email})
    reset_code = verification.last_reset.get(email)
    assert reset_code
    r = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": reset_code, "new_password": "New!Pass#word8"},
    )
    assert r.status_code == 200
    rows = _audit_rows("reset_password", "OK")
    assert rows, "expected a reset_password audit row"
