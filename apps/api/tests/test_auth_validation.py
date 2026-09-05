"""Validation-focused auth tests: university email domains + name/username rules.

The signup email field only accepts university/academic domains:
    *.edu                 (US/world — harvard.edu, mit.edu)
    *.edu.<country-code>  (Egypt .edu.eg, Saudi .edu.sa, UAE .edu.ae, ...)
    *.ac.<country-code>   (UK .ac.uk, etc.)

Run with: python -m pytest tests/test_auth_validation.py -v
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import auth as auth_router


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _signup(client: TestClient, email: str) -> int:
    auth_router._signup_attempts.clear()  # per-case isolation (limit is 3/hour/IP)
    t = int(time.time())
    return client.post(
        "/api/auth/signup",
        json={
            "name": "Validation Test",
            "username": f"val{t}_{abs(hash(email)) % 1000000}",
            "email": email,
            "password": "Str0ng!Pass#word",
        },
    ).status_code


def test_accepts_bare_edu_domain(client):
    assert _signup(client, f"student{int(time.time())}@harvard.edu") == 201
    assert _signup(client, f"student{int(time.time())}@mit.edu") == 201


def test_accepts_edu_country_code_domains(client):
    assert _signup(client, f"student{int(time.time())}@cu.edu.eg") == 201
    assert _signup(client, f"student{int(time.time())}@eng.asu.edu.eg") == 201
    assert _signup(client, f"student{int(time.time())}@ksu.edu.sa") == 201
    assert _signup(client, f"student{int(time.time())}@uaeu.ac.ae") == 201


def test_accepts_ac_country_code_domains(client):
    assert _signup(client, f"student{int(time.time())}@imperial.ac.uk") == 201


def test_accepts_admin_university_subdomains(client):
    assert _signup(client, f"trainer{int(time.time())}@university.edu.eg") == 201
    assert _signup(client, f"study{int(time.time())}@student.university.edu.eg") == 201


@pytest.mark.parametrize(
    "domain",
    [
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "example.com",
        "hotmail.com",
    ],
)
def test_rejects_consumer_email_providers(client, domain):
    assert _signup(client, f"user{int(time.time())}@{domain}") == 422


@pytest.mark.parametrize(
    "domain",
    [
        "evil.edu.eg.com",  # edu.eg in the middle — final TLD is .com
        "foo.edu.eg.attacker.net",  # trailing .net after edu.eg
        "harvard.edu.cm.evil",  # junk after the edu tail
        "x.edu.e",  # country code too short
        "a.b.c.education",  # .education is NOT the .edu TLD
    ],
)
def test_rejects_attacker_domain_tricks(client, domain):
    assert _signup(client, f"user{int(time.time())}@{domain}") == 422


def test_name_whitespace_only_rejected(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "   ",
            "username": f"nm{int(time.time())}",
            "email": f"nm{int(time.time())}@cu.edu.eg",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 422


def test_name_requires_a_letter(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "1234567",
            "username": f"nm{int(time.time())}",
            "email": f"nm{int(time.time())}@cu.edu.eg",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 422


def test_username_max_length_rejected(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "name": "Valid Name",
            "username": "a" * 51,
            "email": f"nm{int(time.time())}@cu.edu.eg",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 422


def test_username_disallows_spaces_and_hyphens(client):
    t = int(time.time())
    for bad_username in (f"bad name{t}", f"bad-name{t}"):
        r = client.post(
            "/api/auth/signup",
            json={
                "name": "Valid Name",
                "username": bad_username,
                "email": f"nm{t}@cu.edu.eg",
                "password": "Str0ng!Pass#word",
            },
        )
        assert r.status_code == 422
