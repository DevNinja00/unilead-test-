"""Pydantic schemas for auth requests + responses."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class SignUpRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_password_strength(self) -> "SignUpRequest":
        pw = self.password
        errors = []
        if not any(c.isupper() for c in pw):
            errors.append("at least one uppercase letter")
        if not any(c.islower() for c in pw):
            errors.append("at least one lowercase letter")
        if not any(c.isdigit() for c in pw):
            errors.append("at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pw):
            errors.append("at least one special character")
        if errors:
            raise ValueError(f"Password must contain {', '.join(errors)}.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Returned on signup/login — the JWT + the user's basic profile."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    username: str
    name: str
    student_id: str


class MeResponse(BaseModel):
    user_id: int
    email: str
    username: str
    name: str
    student_id: str
    student_display_name: str
