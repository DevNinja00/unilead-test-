"""Pydantic schemas for auth requests + responses."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Returned on signup/login — the JWT + the user's basic profile."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    name: str
    student_id: str


class MeResponse(BaseModel):
    user_id: int
    email: str
    name: str
    student_id: str
    student_display_name: str
