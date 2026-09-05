"""Password hashing (bcrypt) and JWT token utilities.

Uses the ``bcrypt`` library directly (instead of passlib) to avoid
compatibility issues with newer bcrypt releases. The hash format is
standard bcrypt (``$2b$...``).
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from ..config import Settings

_settings = Settings()

# --- Password hashing ------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt (cost factor 12)."""
    # bcrypt limits passwords to 72 bytes; truncate if needed (rare for real
    # passwords, but defensive).
    pw_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Verify a password against a stored bcrypt hash."""
    if not hashed:
        return False
    try:
        pw_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_password_timing_resistant(plain: str, hashed: str | None) -> bool:
    """Verify password, but always run a dummy bcrypt check when the hash
    is missing or invalid to prevent timing side-channel attacks.
    """
    if not hashed:
        # Run a dummy bcrypt check so the timing is the same as a valid hash
        bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=12))
        return False
    try:
        pw_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Run dummy check on error to avoid leaking timing info
        with contextlib.suppress(Exception):
            bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=12))
        return False


# --- JWT -------------------------------------------------------------------
def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    token_version: int = 0,
) -> str:
    """Issue a JWT for ``subject`` (the user id).

    ``token_version`` is the user's ``token_version`` at issue time. When it
    changes (e.g. after a password reset) every previously issued token is
    rejected by ``get_current_user``.
    """
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes or _settings.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "iss": "unilead-api",
        "jti": uuid.uuid4().hex,
        "ver": token_version,
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token_claims(token: str) -> dict | None:
    """Decode + validate a JWT, returning the full claims dict or None."""
    try:
        payload = jwt.decode(
            token,
            _settings.jwt_secret,
            algorithms=[_settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iss", "iat", "jti"]},
        )
        if payload.get("iss") != "unilead-api":
            return None
        return payload
    except JWTError:
        return None


def decode_access_token(token: str) -> str | None:
    """Decode a JWT and return the subject (user id as string) or None."""
    payload = decode_token_claims(token)
    if payload is None:
        return None
    return payload.get("sub")
