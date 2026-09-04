"""Ollama provider backed by Ollama's ``/api/chat`` HTTP endpoint."""

from __future__ import annotations

from typing import Any, Optional

from ai_education.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)
from ai_education.llm.config import LLMConfig


class OllamaProvider(LLMProvider):
    """Chats with a local Ollama server through a plain HTTP client."""

    def __init__(
        self,
        config: LLMConfig,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        super().__init__(config)
        import httpx

        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.request_timeout)
        )

    @classmethod
    def _expected_provider_type(cls) -> str:
        return "ollama"

    def _endpoint_url(self) -> str:
        base_url = self.config.base_url
        if not base_url:
            raise LLMProviderError(
                "LLMConfig.base_url is required for the Ollama provider "
                "(no local endpoint is hardcoded)"
            )
        return f"{base_url.rstrip('/')}/api/chat"

    def _build_payload(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.config.model_name),
            "messages": self._serialize_messages(messages),
            "stream": False,
            "options": {
                "temperature": kwargs.pop("temperature", self.config.temperature),
                "num_predict": kwargs.pop("num_predict", self.config.max_tokens),
            },
        }
        if "format" in kwargs:
            payload["format"] = kwargs["format"]
        return payload

    async def generate(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        import httpx

        payload = self._build_payload(messages, **kwargs)
        try:
            response = await self._client.post(self._endpoint_url(), json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        try:
            content: str = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMProviderError(
                f"Malformed Ollama response (missing message.content): {data!r}"
            ) from exc
        return LLMResponse(
            content=content,
            raw_response=data,
            model_name=self.config.model_name,
        )

    async def generate_structured(
        self, messages: list[LLMMessage], response_schema: type[Any]
    ) -> Any:
        response = await self.generate(messages, format="json")
        return self._coerce(response.content, response_schema)

    async def aclose(self) -> None:
        """Close the owned HTTP client (no-op when a client was injected)."""
        if self._owns_client:
            import httpx

            if isinstance(self._client, httpx.AsyncClient):
                await self._client.aclose()