"""Abstract LLM provider interface and shared message/response models.

The provider layer is fully decoupled from the domain: it never imports
competency or evidence schemas and never hardcodes endpoints. Concrete
providers (Ollama, OpenAI, Mock) implement the two abstract async methods.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from ai_education.llm.config import LLMConfig


class LLMProviderError(RuntimeError):
    """Base error for any LLM provider failure (network, config, parsing)."""


class LLMStructureError(LLMProviderError):
    """Raised when a provider response cannot be coerced into a schema."""


class LLMMessage(BaseModel):
    """A single chat turn in a provider-agnostic format."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    """A provider-agnostic completion result."""

    content: str
    raw_response: Optional[dict] = None
    model_name: str = ""


T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract base class for LLM backends."""

    def __init__(self, config: LLMConfig) -> None:
        if config.provider_type != self._expected_provider_type():
            raise LLMProviderError(
                f"Provider type {config.provider_type!r} does not match "
                f"{self.__class__.__name__}"
            )
        self.config: LLMConfig = config

    @classmethod
    def _expected_provider_type(cls) -> str:
        raise NotImplementedError

    @staticmethod
    def _serialize_messages(messages: list[LLMMessage]) -> list[dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in messages]

    @abstractmethod
    async def generate(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        """Generate a free-form completion from the given messages."""

    @abstractmethod
    async def generate_structured(
        self, messages: list[LLMMessage], response_schema: type[T]
    ) -> T:
        """Generate a completion coerced into ``response_schema``."""

    @staticmethod
    def _coerce(content: str, response_schema: type[T]) -> T:
        """Parse JSON ``content`` into ``response_schema`` or raise."""
        try:
            return response_schema.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise LLMStructureError(
                f"Could not parse provider content into "
                f"{response_schema.__name__}: {exc}"
            ) from exc