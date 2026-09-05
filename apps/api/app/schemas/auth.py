"""Pydantic schemas for auth requests + responses."""

from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# University/academic email domains. Accepted tails:
#   *.edu                      (US/world: harvard.edu, mit.edu)
#   *.edu.<country-code>       (Egypt .edu.eg, Saudi .edu.sa, UAE .edu.ae, ...)
#   *.ac.<country-code>        (UK .ac.uk, Japan .ac.jp, India .ac.in, ...)
# The tail is anchored to the end of the domain, so attacker tricks like
# ``name.edu.eg.evil.com`` (final TLD is *not* edu/ac) are rejected.
UNIVERSITY_EMAIL_DOMAIN_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*"
    r"\.(?:edu|edu\.[a-z]{2}|ac\.[a-z]{2})$",
    re.IGNORECASE,
)


class SignUpRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name must not be blank.")
        if not any(c.isalpha() for c in stripped):
            raise ValueError("Name must contain at least one letter.")
        return stripped

    @field_validator("email")
    @classmethod
    def email_must_be_university(cls, v: str) -> str:
        domain = v.rsplit("@", 1)[-1].lower()
        if not UNIVERSITY_EMAIL_DOMAIN_RE.fullmatch(domain):
            raise ValueError(
                "Email must be a university email ending in .edu, .edu.<country>, "
                "or .ac.<country> (e.g. you@university.edu, you@cu.edu.eg, you@university.ac.uk)."
            )
        return v

    @model_validator(mode="after")
    def validate_password_strength(self) -> SignUpRequest:
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
    password: str = Field(..., max_length=72)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class SignUpResponse(BaseModel):
    """Returned by /signup — the code is emailed, the JWT comes after verify."""

    verification_required: bool = True
    email: str
    message: str
    resend_after_seconds: int


class VerifiedResponse(BaseModel):
    """Returned by /verify-email, /resend-verification."""

    email: str
    message: str
    resend_after_seconds: int


class AuthResponse(BaseModel):
    """Returned on verified login/verify — the JWT + the user's basic profile."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    username: str
    name: str
    student_id: str
    role: str = "student"


class MeResponse(BaseModel):
    user_id: int
    email: str
    username: str
    name: str
    student_id: str
    student_display_name: str
    role: str = "student"
