"""End-to-end tests for the email-verification flow.

Covers: signup requires verification (no token), wrong/expired codes
rejected, successful verify then login, already-verified rejection,
resend cooldown, and resend issuing a fresh code.
"""

import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, crud
from app.main import app
from app.services import verification


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _signup(client: TestClient, prefix: str) -> str:
    """Sign up a fresh user, return the email."""
    t = int(time.time())
    email = f"{prefix}{t}@university.edu.eg"
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "Verify Flow Test",
            "username": f"{prefix}{t}",
            "email": email,
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201, f"signup failed: {r.text}"
    return email


def _code_for(email: str) -> str:
    code = verification.last_sent.get(email)
    assert code, f"no verification code recorded for {email}"
    return code


def _backdate_sent_at(email: str, minutes: int = 5) -> None:
    """Push the resend cooldown timestamp so a resend is allowed."""
    with SessionLocal() as db:
        user = crud.get_user_by_email(db, email)
        assert user is not None
        user.email_verification_sent_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            minutes=minutes
        )
        db.commit()


def test_signup_requires_verification_no_token(client):
    email = _signup(client, "vtrq_")
    # Verify the signup response itself: no token, verification required.
    t = int(time.time())
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "Verify Flow Test",
            "username": f"vtrq_b{t}",
            "email": f"vtrq_b{t}@university.edu.eg",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201
    assert r.json()["verification_required"] is True
    assert "access_token" not in r.json()
    # A code was dispatched (and is recoverable in log backend for dev/tests).
    assert verification.last_sent.get(email)


def test_verify_with_wrong_code_rejected(client):
    email = _signup(client, "vtwr_")
    r = client.post("/api/auth/verify-email", json={"email": email, "code": "000000"})
    assert r.status_code == 400
    assert "verification code" in r.json()["detail"].lower()


def test_verify_with_expired_code_rejected(client):
    email = _signup(client, "vtex_")
    code = verification.last_sent.get(email)
    assert code

    # Expire the code in the DB, then the real code must be rejected.
    with SessionLocal() as db:
        user = crud.get_user_by_email(db, email)
        assert user is not None
        user.email_verification_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            minutes=1
        )
        db.commit()

    r = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


def test_verify_then_login_succeeds(client):
    email = _signup(client, "vtok_")
    code = _code_for(email)
    r = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 200
    assert "access_token" in r.json()

    r = client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Pass#word"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_blocked_until_verified(client):
    email = _signup(client, "vtun_")
    r = client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Pass#word"})
    assert r.status_code == 403
    assert "not verified" in r.json()["detail"].lower()


def test_already_verified_rejects_verify_attempt(client):
    email = _signup(client, "vtal_")
    code = _code_for(email)
    assert (
        client.post("/api/auth/verify-email", json={"email": email, "code": code}).status_code
        == 200
    )
    r = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 400
    assert "already verified" in r.json()["detail"].lower()


def test_resend_within_cooldown_rejected(client):
    email = _signup(client, "vtcd_")
    r = client.post("/api/auth/resend-verification", json={"email": email})
    assert r.status_code == 429
    assert "wait" in r.json()["detail"].lower()


def test_resend_after_cooldown_issues_fresh_code(client):
    email = _signup(client, "vtrs_")
    old_code = _code_for(email)

    _backdate_sent_at(email, minutes=5)

    r = client.post("/api/auth/resend-verification", json={"email": email})
    assert r.status_code == 200
    new_code = _code_for(email)
    assert new_code != old_code  # a brand-new code was sent


def test_resend_unknown_email_is_400(client):
    r = client.post(
        "/api/auth/resend-verification",
        json={"email": "nobody-invalid@university.edu.eg"},
    )
    assert r.status_code == 400


def test_verify_unknown_email_is_400(client):
    r = client.post(
        "/api/auth/verify-email",
        json={"email": "nobody-invalid@university.edu.eg", "code": "123456"},
    )
    assert r.status_code == 400
