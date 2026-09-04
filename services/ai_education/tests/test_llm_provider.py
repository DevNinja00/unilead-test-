"""Tests for the LLM provider abstraction layer."""

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, ValidationError

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


def run(coro) -> object:
    """Run an async coroutine to completion (no pytest-asyncio needed)."""
    return asyncio.run(coro)


class CoachGoal(BaseModel):
    """Small schema for structured-response tests."""

    goal: str
    competencies: list[str]


def messages(*texts: str) -> list[LLMMessage]:
    return [LLMMessage(role="user", content=text) for text in texts]


class TestLLMConfig:
    def test_default_initialization(self) -> None:
        config = LLMConfig(provider_type="mock", model_name="mock-model")

        assert config.provider_type == "mock"
        assert config.model_name == "mock-model"
        assert config.temperature == 0.2
        assert config.max_tokens == 1000
        assert config.request_timeout == 30.0
        assert config.base_url is None
        assert config.api_key is None

    def test_invalid_provider_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(provider_type="claude", model_name="x")

    def test_temperature_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(provider_type="mock", model_name="x", temperature=2.5)

    def test_zero_max_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(provider_type="mock", model_name="x", max_tokens=0)


class TestMockTextGeneration:
    def test_queued_text_returns_content_and_model_name(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        provider.queue_response("Hello from the mock")

        response = run(provider.generate(messages("hi")))

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from the mock"
        assert response.model_name == "mock-model"

    def test_queued_dict_is_serialized_as_content(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model"),
            responses=[{"answer": 42}],
        )

        response = run(provider.generate(messages("hi")))

        assert json.loads(response.content) == {"answer": 42}
        assert response.raw_response == {"answer": 42}

    def test_queued_pydantic_instance_round_trips(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model"),
            responses=[CoachGoal(goal="Tune the PID", competencies=["MEC271-PID-TUNE"])],
        )

        response = run(provider.generate(messages("hi")))

        assert json.loads(response.content) == {
            "goal": "Tune the PID",
            "competencies": ["MEC271-PID-TUNE"],
        }


class TestMockStructuredGeneration:
    def test_queued_instance_returned_directly(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        expected = CoachGoal(goal="Learn feedback", competencies=["MEC271-FB"])
        provider.queue_response(expected)

        result = run(provider.generate_structured(messages("hi"), CoachGoal))

        assert result == expected

    def test_queued_json_string_parsed_into_schema(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        provider.queue_response('{"goal": "Master PID", "competencies": ["MEC271-PID-FUND"]}')

        result = run(provider.generate_structured(messages("hi"), CoachGoal))

        assert isinstance(result, CoachGoal)
        assert result.goal == "Master PID"
        assert result.competencies == ["MEC271-PID-FUND"]

    def test_unparseable_queued_response_raises_structure_error(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        provider.queue_response("i am not json")

        with pytest.raises(LLMStructureError):
            run(provider.generate_structured(messages("hi"), CoachGoal))

    def test_wrong_schema_raises_structure_error(self) -> None:
        class OtherPlan(BaseModel):
            unrelated: int

        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        provider.queue_response(OtherPlan(unrelated=7))

        with pytest.raises(LLMStructureError):
            run(provider.generate_structured(messages("hi"), CoachGoal))


class TestAsyncInterface:
    def test_generate_is_an_async_coroutine_function(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        assert asyncio.iscoroutinefunction(provider.generate)
        assert asyncio.iscoroutinefunction(provider.generate_structured)

    def test_empty_queue_raises_provider_error(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )

        with pytest.raises(LLMProviderError, match="queue is empty"):
            run(provider.generate(messages("hi")))

    def test_messages_are_serialized_role_and_content(self) -> None:
        provider = MockLLMProvider(
            LLMConfig(provider_type="mock", model_name="mock-model")
        )
        provider.queue_response("ok")
        msgs = messages("system prompt", "user query")
        msgs.insert(0, LLMMessage(role="system", content="You are a coach"))

        run(provider.generate(msgs))

        assert provider._serialize_messages(msgs) == [
            {"role": "system", "content": "You are a coach"},
            {"role": "user", "content": "system prompt"},
            {"role": "user", "content": "user query"},
        ]


class TestProviderTypeGuarding:
    def test_mock_rejects_mismatched_provider_type(self) -> None:
        with pytest.raises(LLMProviderError):
            MockLLMProvider(
                LLMConfig(provider_type="ollama", model_name="llama3")
            )

    def test_ollama_rejects_mismatched_provider_type(self) -> None:
        with pytest.raises(LLMProviderError):
            OllamaProvider(
                LLMConfig(provider_type="mock", model_name="llama3")
            )


class TestOllamaProviderOffline:
    def test_chat_request_to_api_chat_endpoint(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            assert captured["body"]["stream"] is False
            return httpx.Response(
                200,
                json={
                    "model": "llama3",
                    "message": {"role": "assistant", "content": "ollama says hi"},
                },
            )

        provider = OllamaProvider(
            LLMConfig(
                provider_type="ollama",
                model_name="llama3",
                base_url="http://localhost:11434",
            ),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        response = run(provider.generate(messages("react to feedback?")))

        assert captured["url"] == "http://localhost:11434/api/chat"
        assert response.content == "ollama says hi"
        assert response.model_name == "llama3"

    def test_base_url_missing_raises(self) -> None:
        provider = OllamaProvider(
            LLMConfig(provider_type="ollama", model_name="llama3")
        )

        with pytest.raises(LLMProviderError, match="base_url"):
            run(provider.generate(messages("hi")))

    def test_http_error_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="server exploded")

        provider = OllamaProvider(
            LLMConfig(
                provider_type="ollama",
                model_name="llama3",
                base_url="http://localhost:11434",
            ),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        with pytest.raises(LLMProviderError, match="Ollama request failed"):
            run(provider.generate(messages("hi")))

    def test_structured_path_extracts_and_coerces_json(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": '{"goal": "G1", "competencies": []}',
                    }
                },
            )

        provider = OllamaProvider(
            LLMConfig(
                provider_type="ollama",
                model_name="llama3",
                base_url="http://localhost:11434",
            ),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        result = run(provider.generate_structured(messages("plan"), CoachGoal))

        assert isinstance(result, CoachGoal)
        assert result.goal == "G1"


class TestOpenAIProviderOffline:
    def test_chat_completions_request_with_bearer_auth(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "openai says hi",
                            }
                        }
                    ]
                },
            )

        provider = OpenAIProvider(
            LLMConfig(
                provider_type="openai",
                model_name="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                api_key="sk-test-123",
            ),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        response = run(provider.generate(messages("help me")))

        assert captured["url"] == "https://api.openai.com/v1/chat/completions"
        assert captured["auth"] == "Bearer sk-test-123"
        assert captured["body"]["model"] == "gpt-4o-mini"
        assert captured["body"]["stream"] is False
        assert response.content == "openai says hi"

    def test_api_key_missing_raises(self) -> None:
        provider = OpenAIProvider(
            LLMConfig(
                provider_type="openai",
                model_name="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
            )
        )

        with pytest.raises(LLMProviderError, match="api_key"):
            run(provider.generate(messages("hi")))

    def test_malformed_response_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": []})

        provider = OpenAIProvider(
            LLMConfig(
                provider_type="openai",
                model_name="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                api_key="sk-test-123",
            ),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        with pytest.raises(LLMProviderError, match="Malformed OpenAI response"):
            run(provider.generate(messages("hi")))

    def test_structured_path_requests_json_object(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": '{"goal": "G2", "competencies": ["MEC271-FB"]}',
                            }
                        }
                    ]
                },
            )

        provider = OpenAIProvider(
            LLMConfig(
                provider_type="openai",
                model_name="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                api_key="sk-test-123",
            ),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        result = run(provider.generate_structured(messages("plan"), CoachGoal))

        assert captured["body"]["response_format"] == {"type": "json_object"}
        assert isinstance(result, CoachGoal)
        assert result.competencies == ["MEC271-FB"]