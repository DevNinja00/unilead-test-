"""LLM provider layer: config, abstract interface, and implementations.

Providers are decoupled from the domain model so the AI Coach can swap
between ``OllamaProvider`` (local), ``OpenAIProvider`` (cloud), and
``MockLLMProvider`` (offline tests) without touching coaching logic.
"""

from ai_education.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMStructureError,
)
from ai_education.llm.config import LLMConfig
from ai_education.llm.mock import MockLLMProvider
from ai_education.llm.ollama import OllamaProvider
from ai_education.llm.openai import OpenAIProvider

__all__ = [
    "LLMConfig",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "LLMStructureError",
    "MockLLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
]