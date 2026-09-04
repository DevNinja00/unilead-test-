"""Shared test fixtures for the Unilead API test suite."""

import pytest


@pytest.fixture(autouse=True)
def _clear_rate_limiters():
    """Reset in-memory rate limiters between every test to avoid 429s."""
    from app.routers import auth as auth_router

    auth_router._login_attempts.clear()
    auth_router._signup_attempts.clear()
    yield
    auth_router._login_attempts.clear()
    auth_router._signup_attempts.clear()
