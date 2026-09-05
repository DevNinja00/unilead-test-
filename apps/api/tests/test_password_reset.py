"""End-to-end tests for the password-reset flow.

Covers: generic anti-enumeration response for unknown emails, resetting a
password and logging in with the new one, revocation of previously issued
tokens after a reset, wrong/expired/single-use codes, and password-strength
validation on the new password.
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


def _signup_and_verify(client: TestClient, prefix: str) -> tuple[str, str]:
    """Sign up + verify a fresh user, return (access_token, email)."""
    t = int(time.time())
    email = f"{prefix}{t}@university.edu.eg"
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "Reset Flow Test",
            "username": f"{prefix}{t}",
            "email": email,
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201, f"signup failed: {r.text}"
    code = verification.last_sent.get(email)
    assert code, "no verification code recorded"
    r = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 200, f"verify failed: {r.text}"
    return r.json()["access_token"], email


def test_forgot_password_unknown_email_is_generic_200(client):
    r = client.post("/api/auth/forgot-password", json={"email": "nobody-reset@university.edu.eg"})
    assert r.status_code == 200
    assert "check your inbox" in r.json()["message"].lower()


def test_forgot_password_records_code_in_log_backend(client):
    _, email = _signup_and_verify(client, "fpcb_")
    r = client.post("/api/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    code = verification.last_reset.get(email)
    assert code, "no password-reset code recorded"


def test_reset_password_then_login_with_new_password(client):
    token, email = _signup_and_verify(client, "rpok_")

    client.post("/api/auth/forgot-password", json={"email": email})
    code = verification.last_reset.get(email)
    assert code

    r = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": code, "new_password": "New!Pass#word2"},
    )
    assert r.status_code == 200, f"reset failed: {r.text}"

    # New password logs in; old password no longer does.
    r = client.post("/api/auth/login", json={"email": email, "password": "New!Pass#word2"})
    assert r.status_code == 200
    r = client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Pass#word"})
    assert r.status_code == 401


def test_reset_password_revokes_old_tokens(client):
    token, email = _signup_and_verify(client, "rprev_")
    # Old token works before the reset.
    old = client.get("/api/competencies", headers={"Authorization": f"Bearer {token}"})
    assert old.status_code == 200

    client.post("/api/auth/forgot-password", json={"email": email})
    code = verification.last_reset.get(email)
    r = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": code, "new_password": "New!Pass#word3"},
    )
    assert r.status_code == 200

    # token_version was bumped → the old JWT is rejected with 401.
    revoked = client.get("/api/competencies", headers={"Authorization": f"Bearer {token}"})
    assert revoked.status_code == 401


def test_reset_password_wrong_code_rejected(client):
    _, email = _signup_and_verify(client, "rpwc_")
    client.post("/api/auth/forgot-password", json={"email": email})
    r = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": "000000", "new_password": "New!Pass#word4"},
    )
    assert r.status_code == 400
    assert "reset code" in r.json()["detail"].lower()


def test_reset_password_expired_code_rejected(client):
    _, email = _signup_and_verify(client, "rpex_")
    client.post("/api/auth/forgot-password", json={"email": email})
    code = verification.last_reset.get(email)
    assert code

    with SessionLocal() as db:
        user = crud.get_user_by_email(db, email)
        assert user is not None
        user.password_reset_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            minutes=1
        )
        db.commit()

    r = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": code, "new_password": "New!Pass#word5"},
    )
    assert r.status_code == 400


def test_reset_password_code_is_single_use(client):
    _, email = _signup_and_verify(client, "rpsu_")
    client.post("/api/auth/forgot-password", json={"email": email})
    code = verification.last_reset.get(email)
    assert code

    payload = {"email": email, "code": code, "new_password": "New!Pass#word6"}
    assert client.post("/api/auth/reset-password", json=payload).status_code == 200
    # Reusing the same code must fail (single-use).
    assert client.post("/api/auth/reset-password", json=payload).status_code == 400


def test_reset_password_rejects_weak_new_password(client):
    _, email = _signup_and_verify(client, "rprw_")
    client.post("/api/auth/forgot-password", json={"email": email})
    code = verification.last_reset.get(email)
    assert code

    r = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": code, "new_password": "weakpassword1"},
    )
    assert r.status_code == 422


def test_reset_password_unknown_email_is_400(client):
    r = client.post(
        "/api/auth/reset-password",
        json={
            "email": "nobody-reset2@university.edu.eg",
            "code": "123456",
            "new_password": "New!Pass#word7",
        },
    )
    assert r.status_code == 400
