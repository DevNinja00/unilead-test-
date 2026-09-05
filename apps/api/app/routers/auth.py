"""Auth router — signup, verify-email, resend, login, /me.

Signup flow:
  1. Validate email is unique
  2. Hash password (bcrypt)
  3. Create User row (email_verified=False) + Student row
  4. Seed the student's CompetencySnapshots with the MEC271 initial state
  5. Email a 6-digit verification code (hash + expiry stored on the user)
  6. Return SignUpResponse — NO JWT until the code is verified

Verify flow:
  1. /verify-email checks the code (constant-time) + expiry
  2. Marks the user verified, returns JWT + student_id

Resend flow:
  1. /resend-verification reissues a code, respecting a cooldown window
     (so an address can't be flooded).

Login flow:
  1. Find user by email (timing-resistant even for unknown emails)
  2. Verify password
  3. If verified: return JWT + student_id
  4. If not verified: 403 -> client routes to the verification screen
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.service import create_access_token, hash_password, verify_password_timing_resistant
from ..config import Settings
from ..db import crud, get_db
from ..db.bootstrap import get_default_section_id
from ..db.models import User
from ..schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignUpRequest,
    SignUpResponse,
    VerifiedResponse,
    VerifyEmailRequest,
)
from ..services import verification
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

# --- Simple in-memory rate limiter for verify/resend (per-IP) ---------------
_verify_attempts: dict[str, list[float]] = defaultdict(list)
_VERIFY_MAX_ATTEMPTS = Settings().verification_max_attempts
_VERIFY_WINDOW_SECONDS = 60

# --- Simple in-memory rate limiters for forgot/reset-password (per-IP) ------
_forgot_attempts: dict[str, list[float]] = defaultdict(list)
_reset_attempts: dict[str, list[float]] = defaultdict(list)
_FORGOT_WINDOW_SECONDS = 60
_RESET_WINDOW_SECONDS = 60

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
    """Raise 429 if this IP already has too many recent login FAILURES.

    Failure count only — successful logins never count toward the limit,
    and a successful login resets the counter (see ``_reset_login_attempts``).
    """
    _sweep_expired(_login_attempts, _LOGIN_WINDOW_SECONDS)
    now = time.monotonic()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )


def _record_login_failure(ip: str) -> None:
    _login_attempts[ip].append(time.monotonic())


def _reset_login_attempts(ip: str) -> None:
    _login_attempts.pop(ip, None)


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


def _check_verify_rate_limit(ip: str) -> None:
    _sweep_expired(_verify_attempts, _VERIFY_WINDOW_SECONDS)
    now = time.monotonic()
    _verify_attempts[ip] = [t for t in _verify_attempts[ip] if now - t < _VERIFY_WINDOW_SECONDS]
    if len(_verify_attempts[ip]) >= _VERIFY_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please try again later.",
        )
    _verify_attempts[ip].append(now)


def _check_forgot_rate_limit(ip: str) -> None:
    _sweep_expired(_forgot_attempts, _FORGOT_WINDOW_SECONDS)
    now = time.monotonic()
    _forgot_attempts[ip] = [t for t in _forgot_attempts[ip] if now - t < _FORGOT_WINDOW_SECONDS]
    if len(_forgot_attempts[ip]) >= _VERIFY_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    _forgot_attempts[ip].append(now)


def _check_reset_rate_limit(ip: str) -> None:
    _sweep_expired(_reset_attempts, _RESET_WINDOW_SECONDS)
    now = time.monotonic()
    _reset_attempts[ip] = [t for t in _reset_attempts[ip] if now - t < _RESET_WINDOW_SECONDS]
    if len(_reset_attempts[ip]) >= _VERIFY_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )
    _reset_attempts[ip].append(now)


def _sanitize_email(email: str) -> str:
    """Strip non-ASCII chars from email to prevent log injection."""
    return email.encode("ascii", "ignore").decode("ascii")


def _utcnow() -> datetime:
    """Timezone-naive UTC now — matches SQLite's default datetime format."""
    return datetime.now(UTC).replace(tzinfo=None)


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


def _issue_verification_code(db: Session, user: User) -> str:
    """Generate + persist + email a fresh code for ``user``. Returns the TTL."""
    code = verification.generate_code()
    crud.set_user_verification(
        db,
        user=user,
        code_hash=verification.hash_code(code),
        expires_at=_utcnow() + timedelta(seconds=verification.code_ttl_seconds()),
        sent_at=_utcnow(),
    )
    db.commit()
    verification.send_code(user.email, code)
    return code


def _auth_payload(user: User, student_id: str) -> dict:
    token = create_access_token(
        subject=str(user.id),
        token_version=user.token_version,
    )
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


def _audit(
    db: Session,
    *,
    action: str,
    outcome: str,
    ip: str,
    user: User | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str = "",
) -> None:
    """Record one security-relevant event; commits with the current txn."""
    crud.add_audit_log(
        db,
        actor_user_id=user.id if user else None,
        actor_role=(user.role or "student") if user else "anonymous",
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip,
        outcome=outcome,
    )


# --- Routes ----------------------------------------------------------------


@router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignUpRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_signup_rate_limit(ip)

    # Normalize once so uniqueness + login are case-insensitive on the
    # local part too (EmailStr only lowercases the domain, not the mailbox).
    email = req.email.lower()
    username = req.username.lower()

    # 1. Email unique? (case-insensitive)
    if crud.get_user_by_email(db, email) is not None:
        # Use generic message to prevent enumeration
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        )

    # 2. Username unique? (case-insensitive)
    if crud.get_user_by_username(db, username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        )

    # 3. Create user (unverified) + student + seed — in one transaction. The
    # pre-checks above are not atomic against concurrent requests, so a race
    # that slips past them surfaces here as an IntegrityError → 409, not 500.
    try:
        user = crud.create_user(
            db,
            email=email,
            username=username,
            name=req.name.strip(),
            password_hash=hash_password(req.password),
        )
        db.flush()

        # 4. Create student record linked to this user
        student_id = _student_id_for_user(user.id)
        crud.create_student(
            db,
            student_id=student_id,
            user_id=user.id,
            display_name=req.name.strip(),
        )

        # 5. Seed initial competencies
        _seed_initial_competencies(db, student_id)

        # 5b. Tenant-less accounts get automatic data access: enroll the new
        # learner in the default organization's section so student-data and
        # instructor endpoints keep working exactly as before this release.
        section_id = get_default_section_id(db)
        if section_id is not None:
            crud.enroll_student_in_section(db, student_id=student_id, section_id=section_id)

        # 6. Issue the verification code (email it) before committing.
        _issue_verification_code(db, user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        ) from None

    _audit(
        db,
        action="signup",
        outcome="OK",
        ip=ip,
        user=user,
        target_type="user",
        target_id=str(user.id),
        detail=f"signup for {_sanitize_email(email)}",
    )
    db.commit()

    return {
        "verification_required": True,
        "email": user.email,
        "message": f"Verification code sent to {user.email}.",
        "resend_after_seconds": verification_code_cooldown(user),
    }


def verification_code_cooldown(user: User) -> int:
    """Seconds the user must wait before the next resend request."""
    return int(verification.cooldown_remaining(user.email_verification_sent_at))


@router.post(
    "/verify-email",
    response_model=AuthResponse,
    responses={400: {"description": "Invalid/expired code or already verified."}},
)
def verify_email(req: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_verify_rate_limit(ip)

    email = req.email.lower()
    user = crud.get_user_by_email(db, email)
    if user is None:
        # Generic — don't reveal whether the email is registered.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    error_detail = "Invalid or expired verification code."
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already verified. You can log in.",
        )

    stored_hash = user.email_verification_code_hash
    expires_at = user.email_verification_expires_at
    if not stored_hash or expires_at is None or _utcnow() > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    if not verification.verify_code(req.code.strip(), stored_hash):
        # Still run timing-resistant logic — hash compare already constant-time.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail,
        )

    crud.mark_user_verified(db, user=user)
    db.commit()
    _reset_login_attempts(ip)

    students = crud.get_students_by_user_id(db, user.id)
    if not students:
        _audit(
            db,
            action="verify_email",
            outcome="FAILED",
            ip=ip,
            target_type="user",
            target_id=str(user.id),
            detail="verified but no student record",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to this account.",
        )

    _audit(
        db,
        action="verify_email",
        outcome="OK",
        ip=ip,
        user=user,
        target_type="user",
        target_id=str(user.id),
    )
    db.commit()
    return _auth_payload(user, students[0].student_id)


@router.post("/resend-verification", response_model=VerifiedResponse)
def resend_verification(
    req: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_verify_rate_limit(ip)

    email = req.email.lower()
    user = crud.get_user_by_email(db, email)
    if user is None:
        # Generic — don't reveal whether the email is registered.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending verification for that email.",
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already verified. You can log in.",
        )

    # Resend cooldown — an address can't be bombarded with codes.
    remain = verification.cooldown_remaining(user.email_verification_sent_at)
    if remain > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {int(remain) + 1} seconds before requesting another code.",
        )

    _issue_verification_code(db, user)
    _audit(
        db,
        action="resend_verification",
        outcome="OK",
        ip=ip,
        user=user,
        target_type="user",
        target_id=str(user.id),
    )
    db.commit()
    return {
        "email": user.email,
        "message": f"Verification code sent to {user.email}.",
        "resend_after_seconds": verification_code_cooldown(user),
    }


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(ip)

    user = crud.get_user_by_email(db, req.email)
    # Always run the dummy-bcrypt timing-resistant check — even for unknown
    # emails — so account existence can't be probed via response timing.
    valid = verify_password_timing_resistant(req.password, user.password_hash if user else None)
    if not valid:
        _record_login_failure(ip)
        _log.warning("Failed login attempt for email=%s from ip=%s", _sanitize_email(req.email), ip)
        if user is not None:
            _audit(
                db,
                action="login",
                outcome="FAILED",
                ip=ip,
                user=user,
                target_type="user",
                target_id=str(user.id),
                detail=f"wrong password for {_sanitize_email(req.email)}",
            )
        else:
            _audit(
                db,
                action="login",
                outcome="FAILED",
                ip=ip,
                target_type="email",
                target_id=_sanitize_email(req.email),
                detail="unknown account",
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 429s are for brute force; a successful password shows this IP is legit.
    _reset_login_attempts(ip)

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the verification code.",
        )

    # Find the student record linked to this user.
    students = crud.get_students_by_user_id(db, user.id)
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to this account.",
        )

    _audit(
        db,
        action="login",
        outcome="OK",
        ip=ip,
        user=user,
        target_type="user",
        target_id=str(user.id),
    )
    db.commit()
    return _auth_payload(user, students[0].student_id)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Request a password-reset code for an account.

    The response is identical whether or not the account exists
    (anti-enumeration); only rate limiting and a per-email cooldown can
    reveal activity, and both are bounded.
    """
    ip = request.client.host if request.client else "unknown"
    _check_forgot_rate_limit(ip)

    email = req.email.lower()
    user = crud.get_user_by_email(db, email)
    generic = {
        "message": (
            "If an account exists for that email, a password-reset code "
            "has been sent. Check your inbox."
        ),
        "resend_after_seconds": _RESET_WINDOW_SECONDS,
    }

    if user is None:
        _audit(
            db,
            action="forgot_password",
            outcome="OK",
            ip=ip,
            target_type="email",
            target_id=_sanitize_email(email),
            detail="no account for this email (generic response)",
        )
        db.commit()
        return generic

    # Per-email cooldown so an address can't be flooded with reset emails.
    remain = verification.cooldown_remaining(user.password_reset_sent_at)
    if remain > 0:
        generic["resend_after_seconds"] = int(remain) + 1
        _audit(
            db,
            action="forgot_password",
            outcome="RATELIMITED",
            ip=ip,
            user=user,
            target_type="user",
            target_id=str(user.id),
        )
        db.commit()
        return generic

    code = verification.generate_code()
    crud.set_user_password_reset(
        db,
        user=user,
        code_hash=verification.hash_code(code),
        expires_at=_utcnow() + timedelta(seconds=verification.code_ttl_seconds()),
        sent_at=_utcnow(),
    )
    verification.send_password_reset(email, code)
    _audit(
        db,
        action="forgot_password",
        outcome="OK",
        ip=ip,
        user=user,
        target_type="user",
        target_id=str(user.id),
    )
    db.commit()
    return generic


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    req: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Redeem a password-reset code and set a new password.

    Success bumps ``token_version``, which revokes every previously issued
    JWT for the account in one step. Responses are generic so the endpoint
    can't be used to enumerate accounts.
    """
    ip = request.client.host if request.client else "unknown"
    _check_reset_rate_limit(ip)

    email = req.email.lower()
    user = crud.get_user_by_email(db, email)
    error_detail = "Invalid or expired reset code."
    if user is None:
        _audit(
            db,
            action="reset_password",
            outcome="FAILED",
            ip=ip,
            target_type="email",
            target_id=_sanitize_email(email),
            detail="unknown account",
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)

    stored_hash = user.password_reset_code_hash
    expires_at = user.password_reset_expires_at
    if not stored_hash or expires_at is None or _utcnow() > expires_at:
        _audit(
            db,
            action="reset_password",
            outcome="FAILED",
            ip=ip,
            user=user,
            target_type="user",
            target_id=str(user.id),
            detail="missing or expired reset code",
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)

    if not verification.verify_code(req.code.strip(), stored_hash):
        _audit(
            db,
            action="reset_password",
            outcome="FAILED",
            ip=ip,
            user=user,
            target_type="user",
            target_id=str(user.id),
            detail="wrong reset code",
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)

    user.password_hash = hash_password(req.new_password)
    user.last_password_change_at = _utcnow()
    crud.clear_user_password_reset(db, user=user)
    crud.bump_token_version(db, user=user)
    _audit(
        db,
        action="reset_password",
        outcome="OK",
        ip=ip,
        user=user,
        target_type="user",
        target_id=str(user.id),
        detail="password reset; all previous tokens revoked",
    )
    db.commit()

    return {
        "message": "Your password has been reset. Log in with your new password.",
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
