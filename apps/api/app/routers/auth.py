"""Auth router — signup, login, /me.

Signup flow:
  1. Validate email is unique
  2. Hash password (bcrypt)
  3. Create User row
  4. Create a Student row (student_id derived from user_id)
  5. Seed the student's CompetencySnapshots with the MEC271 initial state
  6. Return JWT + student_id

Login flow:
  1. Find user by email
  2. Verify password
  3. Return JWT + student_id
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.service import create_access_token, hash_password, verify_password_timing_resistant
from ..db import crud, get_db
from ..db.models import User
from ..schemas.auth import AuthResponse, LoginRequest, MeResponse, SignUpRequest
from ..services.mock_data import INITIAL_COMPETENCIES

router = APIRouter(prefix="/api/auth", tags=["auth"])

_log = logging.getLogger("unilead.auth")

# --- Simple in-memory rate limiter for login (per-IP, 5 attempts / 60s) -----
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60

# --- Simple in-memory rate limiter for signup (per-IP, 3 per hour) ----------
_signup_attempts: dict[str, list[float]] = defaultdict(list)
_SIGNUP_MAX_ATTEMPTS = 3
_SIGNUP_WINDOW_SECONDS = 3600

# --- Max IPs tracked to prevent memory exhaustion -------------------------
_MAX_TRACKED_IPS = 10_000


def _sweep_expired(attempts: dict[str, list[float]], window: float) -> None:
    """Remove expired entries and cap dict size to prevent memory exhaustion."""
    now = time.monotonic()
    expired = [ip for ip, times in attempts.items() if not times or now - times[-1] >= window]
    for ip in expired:
        del attempts[ip]
    # If still too many IPs, evict oldest
    if len(attempts) > _MAX_TRACKED_IPS:
        sorted_ips = sorted(attempts, key=lambda ip: attempts[ip][-1] if attempts[ip] else 0)
        for ip in sorted_ips[: len(sorted_ips) - _MAX_TRACKED_IPS]:
            del attempts[ip]


def _check_login_rate_limit(ip: str) -> None:
    _sweep_expired(_login_attempts, _LOGIN_WINDOW_SECONDS)
    now = time.monotonic()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )
    _login_attempts[ip].append(now)


def _record_login_attempt(ip: str) -> None:
    _login_attempts[ip].append(time.monotonic())


def _check_signup_rate_limit(ip: str) -> None:
    _sweep_expired(_signup_attempts, _SIGNUP_WINDOW_SECONDS)
    now = time.monotonic()
    _signup_attempts[ip] = [t for t in _signup_attempts[ip] if now - t < _SIGNUP_WINDOW_SECONDS]
    if len(_signup_attempts[ip]) >= _SIGNUP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again later.",
        )
    _signup_attempts[ip].append(now)


def _sanitize_email(email: str) -> str:
    """Strip non-ASCII chars from email to prevent log injection."""
    return email.encode("ascii", "ignore").decode("ascii")

# --- Helpers ---------------------------------------------------------------


def _student_id_for_user(user_id: int) -> str:
    """Derive a stable student_id from the user_id."""
    return f"u{user_id}-student"


def _seed_initial_competencies(db: Session, student_id: str) -> None:
    """Seed the 5 MEC271 competencies at their initial state."""
    for c in INITIAL_COMPETENCIES:
        crud.upsert_competency(
            db,
            student_id=student_id,
            competency_id=c["id"],
            competency_name=c["name"],
            status=c["status"],
            progress=c["progress"],
        )


# --- Routes ----------------------------------------------------------------


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignUpRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_signup_rate_limit(ip)

    # 1. Email unique?
    if crud.get_user_by_email(db, req.email) is not None:
        # Use generic message to prevent enumeration
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        )

    # 2. Username unique?
    if crud.get_user_by_username(db, req.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        )

    # 3. Create user
    user = crud.create_user(
        db,
        email=req.email,
        username=req.username,
        name=req.name,
        password_hash=hash_password(req.password),
    )
    db.flush()

    # 4. Create student record linked to this user
    student_id = _student_id_for_user(user.id)
    crud.create_student(
        db,
        student_id=student_id,
        user_id=user.id,
        display_name=req.name,
    )

    # 5. Seed initial competencies
    _seed_initial_competencies(db, student_id)

    db.commit()

    # 6. Issue JWT
    token = create_access_token(subject=str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.name,
        "student_id": student_id,
        "role": user.role or "student",
    }


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(ip)

    user = crud.get_user_by_email(db, req.email)
    if user is None or not verify_password_timing_resistant(req.password, user.password_hash):
        _log.warning("Failed login attempt for email=%s from ip=%s", _sanitize_email(req.email), ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _record_login_attempt(ip)

    # Find the student record linked to this user.
    students = crud.get_students_by_user_id(db, user.id)
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to this account.",
        )

    token = create_access_token(subject=str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.name,
        "student_id": students[0].student_id,
        "role": user.role or "student",
    }


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    students = crud.get_students_by_user_id(db, current_user.id)
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to this account.",
        )
    s = students[0]
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "name": current_user.name,
        "student_id": s.student_id,
        "student_display_name": s.display_name,
        "role": current_user.role or "student",
    }
