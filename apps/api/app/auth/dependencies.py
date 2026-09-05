"""FastAPI auth dependencies.

Usage in routers:

    from fastapi import Depends
    from sqlalchemy.orm import Session
    from ..auth.dependencies import get_current_user, get_current_student
    from ..db import get_db
    from ..db.models import User, Student

    @router.get("/me")
    def me(current_user: User = Depends(get_current_user)):
        return current_user

    @router.get("/competencies")
    def list_competencies(
        student: Student = Depends(get_current_student),
        db: Session = Depends(get_db),
    ):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..db import crud, get_db, models
from .service import decode_access_token

# auto_error=False so endpoints can choose whether auth is required
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve the JWT bearer token to a User, or 401."""
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_exc
    user_id_str = decode_access_token(token)
    if not user_id_str:
        raise creds_exc
    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        raise creds_exc from None

    user = crud.get_user_by_id(db, user_id)
    if user is None:
        raise creds_exc
    # Defense-in-depth: tokens are only issued after email verification, but
    # block any stray pre-verification token from reaching protected routes.
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the verification code.",
        )
    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Like ``get_current_user`` but returns None instead of 401."""
    if not token:
        return None
    user_id_str = decode_access_token(token)
    if not user_id_str:
        return None
    try:
        user = crud.get_user_by_id(db, int(user_id_str))
    except (TypeError, ValueError):
        return None
    if user is not None and not user.email_verified:
        return None
    return user


def get_current_student(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Student:
    """Resolve the current user's first student record.

    For this MVP each user has exactly one student record. If you add
    multi-student-per-user later, change this to take a ``student_id``
    query param.
    """
    students = crud.get_students_by_user_id(db, current_user.id)
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to this user.",
        )
    return students[0]


def get_current_instructor(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Resolve the current user as an instructor.

    Requires the user to have ``role='instructor'`` in the database.
    """
    if current_user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor access required.",
        )
    return current_user
