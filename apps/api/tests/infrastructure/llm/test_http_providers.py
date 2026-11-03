import json

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from govcheck.domain.llm import ChatMessage, LLMResult, TokenUsage
from govcheck.infrastructure.llm.groq import GroqLLMProvider
from govcheck.infrastructure.llm.ollama import OllamaLLMProvider


class Deadline(BaseModel):
    date: str
    page: int


@pytest.mark.asyncio
async def test_groq_completion_uses_openai_compatible_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openai/v1/chat/completions"
        assert json.loads(request.content) == {
            "model": "llama-test",
            "messages": [{"role": "user", "content": "Prazo?"}],
            "temperature": 0,
        }
        return httpx.Response(
            200,
            json={
                "model": "llama-test",
                "choices": [{"message": {"content": "13 de novembro"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1/",
        headers={"Authorization": "Bearer test"},
    ) as client:
        provider = GroqLLMProvider(
            api_key=SecretStr("test"),
            model="llama-test",
            base_url="https://api.groq.com/openai/v1",
            client=client,
        )

        result = await provider.complete([ChatMessage(role="user", content="Prazo?")])

    assert result == LLMResult(
        text="13 de novembro",
        model="llama-test",
        usage=TokenUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
    )


@pytest.mark.asyncio
async def test_groq_stream_yields_only_text_deltas() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        body = (
            'data: {"choices":[{"delta":{"content":"Prazo "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"final"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1/"
    ) as client:
        provider = GroqLLMProvider(
            api_key=SecretStr("test"),
            model="llama-test",
            base_url=str(client.base_url),
            client=client,
        )

        chunks = [chunk async for chunk in provider.stream([])]

    assert chunks == ["Prazo ", "final"]


@pytest.mark.asyncio
async def test_groq_structured_output_is_validated_by_requested_schema() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"date":"2026-11-13","page":4}'}}]},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1/"
    ) as client:
        provider = GroqLLMProvider(
            api_key=SecretStr("test"),
            model="llama-test",
            base_url=str(client.base_url),
            client=client,
        )

        result = await provider.structured([], Deadline)

    assert result == Deadline(date="2026-11-13", page=4)


@pytest.mark.asyncio
async def test_ollama_completion_maps_usage_counts() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "message": {"content": "13 de novembro"},
                "prompt_eval_count": 5,
                "eval_count": 2,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://localhost:11434/"
    ) as client:
        provider = OllamaLLMProvider(
            base_url=str(client.base_url), model="llama3.2:3b", client=client
        )

        result = await provider.complete([ChatMessage(role="user", content="Prazo?")])

    assert result.usage == TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7)
    assert result.text == "13 de novembro"


@pytest.mark.asyncio
async def test_ollama_stream_reads_newline_delimited_json() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        body = (
            '{"message":{"content":"Prazo "},"done":false}\n'
            '{"message":{"content":"final"},"done":false}\n'
            '{"message":{"content":""},"done":true}\n'
        )
        return httpx.Response(200, text=body)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://localhost:11434/"
    ) as client:
        provider = OllamaLLMProvider(
            base_url=str(client.base_url), model="llama3.2:3b", client=client
        )

        chunks = [chunk async for chunk in provider.stream([])]

    assert chunks == ["Prazo ", "final"]


@pytest.mark.asyncio
async def test_ollama_structured_output_sends_json_schema() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["format"]["required"] == ["date", "page"]
        return httpx.Response(
            200,
            json={"message": {"content": '{"date":"2026-11-13","page":4}'}},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://localhost:11434/"
    ) as client:
        provider = OllamaLLMProvider(
            base_url=str(client.base_url), model="llama3.2:3b", client=client
        )

        result = await provider.structured([], Deadline)

    assert result == Deadline(date="2026-11-13", page=4)
