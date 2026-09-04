"""Unified configuration for the Compass + AI Education gateway.

Combines the original Platform/backend config (CORS origins, host, port)
with the AI Education LLM provider settings (provider type, model, keys).
Everything is read from environment variables (or an optional .env file),
so the server can be launched identically in dev and deployment.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Path bootstrap ---------------------------------------------------------
# Make ``python -m app.main`` and ``uvicorn app.main:app`` work from the
# apps/api directory: insert the ai_education library directory on sys.path
# so its package is importable without pip-installing it.
_APP_DIR = Path(__file__).resolve().parent  # apps/api/app
_API_DIR = _APP_DIR.parent                   # apps/api
_REPO_ROOT = _API_DIR.parents[1]             # unilead-unified/
_AI_EDUCATION_DIR = _REPO_ROOT / "services" / "ai_education"

import sys  # noqa: E402

for _directory in (str(_AI_EDUCATION_DIR), str(_API_DIR)):
    if _directory not in sys.path:
        sys.path.insert(0, _directory)

# Re-export so other modules can use the same paths
AI_EDUCATION_DIR = _AI_EDUCATION_DIR
REPO_ROOT = _REPO_ROOT


DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

LLM_PROVIDER_TYPES = ("mock", "ollama", "openai")


class Settings(BaseSettings):
    """Server + LLM + DB + auth configuration read from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server (Compass API) ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = DEFAULT_ORIGINS

    # --- Database ---
    database_url: str = "sqlite:///./unilead.db"

    # --- Auth (JWT) ---
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # --- LLM provider (AI Education gateway) ---
    llm_provider_type: Literal["mock", "ollama", "openai"] = "mock"
    llm_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"

    # --- AI Education student session ---
    student_id: str = "api-gateway-student"
    course_id: str = "MEC271"


def get_cors_origins() -> list[str]:
    """Return the list of allowed CORS origins (comma-separated string)."""
    return [
        origin.strip()
        for origin in Settings().cors_origins.split(",")
        if origin.strip()
    ]
