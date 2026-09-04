"""LLM provider configuration for the AI Coach."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration describing which provider and model to call.

    Endpoints are deliberately not hardcoded anywhere in this package:
    providers resolve ``base_url`` from this config and refuse to run when
    it is missing.
    """

    provider_type: Literal["ollama", "openai", "mock"]
    model_name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1)
    request_timeout: float = Field(default=30.0, gt=0.0)