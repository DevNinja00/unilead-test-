"""OpenAI-compatible provider backed by the Chat Completions endpoint."""

from __future__ import annotations

from typing import Any, Optional

from ai_education.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)
from ai_education.llm.config import LLMConfig


class OpenAIProvider(LLMProvider):
    """Calls an OpenAI-compatible ``/chat/completions`` endpoint."""

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
        return "openai"

    def _endpoint_url(self) -> str:
        base_url = self.config.base_url
        if not base_url:
            raise LLMProviderError(
                "LLMConfig.base_url is required for the OpenAI provider "
                "(the endpoint is resolved from config, never hardcoded)"
            )
        return f"{base_url.rstrip('/')}/chat/completions"

    def _auth_headers(self) -> dict[str, str]:
        api_key = self.config.api_key
        if not api_key:
            raise LLMProviderError(
                "LLMConfig.api_key is required for the OpenAI provider"
            )
        return {"Authorization": f"Bearer {api_key}"}

    def _build_payload(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.config.model_name),
            "messages": self._serialize_messages(messages),
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            "stream": False,
        }
        if "response_format" in kwargs:
            payload["response_format"] = {"type": kwargs["response_format"]}
        return payload

    async def generate(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        import httpx

        payload = self._build_payload(messages, **kwargs)
        try:
            response = await self._client.post(
                self._endpoint_url(), json=payload, headers=self._auth_headers()
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

        try:
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Malformed OpenAI response (missing choices[0].message.content): "
                f"{data!r}"
            ) from exc
        return LLMResponse(
            content=content,
            raw_response=data,
            model_name=self.config.model_name,
        )

    async def generate_structured(
        self, messages: list[LLMMessage], response_schema: type[Any]
    ) -> Any:
        response = await self.generate(messages, response_format="json_object")
        return self._coerce(response.content, response_schema)

    async def aclose(self) -> None:
        """Close the owned HTTP client (no-op when a client was injected)."""
        if self._owns_client:
            import httpx

            if isinstance(self._client, httpx.AsyncClient):
                await self._client.aclose()