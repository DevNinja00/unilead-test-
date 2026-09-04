"""Auth router — signup, login, /me.

Signup flow:
  1. Validate email is unique
  2. Hash password (bcrypt)
  3. Create User row
  4. Create a Student row (student_id derived from user_id)
  5. Seed the student's CompetencySnapshots with the MEC271 initial state
  6. Return JWT + student_id

Login flow:
  1. Find user by email (404 if not found)
  2. Verify password (401 if wrong)
  3. Return JWT + student_id
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.service import create_access_token, hash_password, verify_password
from ..db import crud, get_db
from ..db.models import User
from ..schemas.auth import AuthResponse, LoginRequest, MeResponse, SignUpRequest
from ..services.mock_data import INITIAL_COMPETENCIES

router = APIRouter(prefix="/api/auth", tags=["auth"])

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
def signup(req: SignUpRequest, db: Session = Depends(get_db)) -> dict:
    # 1. Email unique?
    if crud.get_user_by_email(db, req.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    # 2. Create user
    user = crud.create_user(
        db,
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
    )
    db.flush()

    # 3. Create student record linked to this user
    student_id = _student_id_for_user(user.id)
    crud.create_student(
        db,
        student_id=student_id,
        user_id=user.id,
        display_name=req.name,
    )

    # 4. Seed initial competencies
    _seed_initial_competencies(db, student_id)

    db.commit()

    # 5. Issue JWT
    token = create_access_token(subject=str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "student_id": student_id,
    }


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = crud.get_user_by_email(db, req.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with that email.",
        )
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
        "name": user.name,
        "student_id": students[0].student_id,
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
        "name": current_user.name,
        "student_id": s.student_id,
        "student_display_name": s.display_name,
    }
