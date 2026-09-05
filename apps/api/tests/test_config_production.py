"""Tests for the production configuration fail-fast validation.

The API must refuse to boot in ``env=production`` with placeholder secrets
or log-only email delivery, while development keeps the permissive
zero-config defaults.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            jwt_secret="change-me-in-production-please-use-a-long-random-string",
            email_backend="smtp",
            smtp_host="smtp.university.edu",
        )


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            jwt_secret="too-short",
            email_backend="smtp",
            smtp_host="smtp.university.edu",
        )


def test_production_requires_smtp_backend():
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            jwt_secret="a" * 40,
            email_backend="log",
        )


def test_production_accepts_strong_config():
    secret = "a" * 40
    settings = Settings(
        env="production",
        jwt_secret=secret,
        email_backend="smtp",
        smtp_host="smtp.university.edu",
    )
    assert settings.env == "production"
    assert settings.jwt_secret == secret
    assert settings.email_backend == "smtp"


def test_development_keeps_permissive_defaults():
    settings = Settings()
    assert settings.env == "development"
    assert settings.email_backend == "log"
    assert settings.jwt_secret == "change-me-in-production-please-use-a-long-random-string"
