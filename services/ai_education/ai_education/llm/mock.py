"""Deterministic, offline LLM provider for unit tests and demos.

Queued responses may be raw strings, plain dicts, or full Pydantic
instances. ``generate_structured`` pops the queue and coerces the queued
value into the requested schema, so the AI Coach can be tested offline
without a network dependency.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Union

from pydantic import BaseModel, ValidationError

from ai_education.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMStructureError,
)
from ai_education.llm.config import LLMConfig

QueuedResponse = Union[str, dict, BaseModel]


class MockLLMProvider(LLMProvider):
    """Serves pre-queued responses; never touches the network."""

    def __init__(
        self,
        config: LLMConfig,
        responses: Optional[list[QueuedResponse]] = None,
    ) -> None:
        super().__init__(config)
        self._queue: list[QueuedResponse] = list(responses or [])

    @classmethod
    def _expected_provider_type(cls) -> str:
        return "mock"

    def queue_response(self, response: QueuedResponse) -> None:
        """Append a single canned response to the queue."""
        self._queue.append(response)

    def queue_responses(self, responses: list[QueuedResponse]) -> None:
        """Append several canned responses to the queue, in order."""
        self._queue.extend(responses)

    def pending_count(self) -> int:
        """Number of queued responses not yet consumed."""
        return len(self._queue)

    def _pop(self) -> QueuedResponse:
        if not self._queue:
            raise LLMProviderError("MockLLMProvider response queue is empty")
        return self._queue.pop(0)

    async def generate(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        item = self._pop()
        if isinstance(item, str):
            return LLMResponse(content=item, model_name=self.config.model_name)
        if isinstance(item, BaseModel):
            return LLMResponse(
                content=item.model_dump_json(),
                raw_response=item.model_dump(),
                model_name=self.config.model_name,
            )
        return LLMResponse(
            content=json.dumps(item),
            raw_response=item,
            model_name=self.config.model_name,
        )

    async def generate_structured(
        self, messages: list[LLMMessage], response_schema: type[BaseModel]
    ) -> BaseModel:
        item = self._pop()
        try:
            if isinstance(item, response_schema):
                return item
            if isinstance(item, BaseModel):
                return response_schema.model_validate(item.model_dump())
            if isinstance(item, dict):
                return response_schema.model_validate(item)
            return response_schema.model_validate_json(item)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise LLMStructureError(
                f"Queued mock response could not be coerced into "
                f"{response_schema.__name__}: {exc}"
            ) from exc