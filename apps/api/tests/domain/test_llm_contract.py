from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel, ValidationError

from govcheck.domain.llm import ChatMessage, LLMResult
from govcheck.infrastructure.llm.fake import FakeLLMProvider


class ExtractedDeadline(BaseModel):
    date: str
    page: int


@pytest.mark.asyncio
async def test_fake_provider_returns_configured_completion() -> None:
    provider = FakeLLMProvider(text="Prazo encontrado", model="fake-contract")

    result = await provider.complete([ChatMessage(role="user", content="Qual é o prazo?")])

    assert result == LLMResult(text="Prazo encontrado", model="fake-contract", usage=None)


@pytest.mark.asyncio
async def test_fake_provider_streams_configured_chunks_in_order() -> None:
    provider = FakeLLMProvider(chunks=["Prazo ", "encontrado"])

    stream: AsyncIterator[str] = provider.stream(
        [ChatMessage(role="user", content="Qual é o prazo?")]
    )

    assert [chunk async for chunk in stream] == ["Prazo ", "encontrado"]


@pytest.mark.asyncio
async def test_fake_provider_validates_structured_output() -> None:
    provider = FakeLLMProvider(structured_payload={"date": "2026-11-13", "page": 4})

    result = await provider.structured([], ExtractedDeadline)

    assert result == ExtractedDeadline(date="2026-11-13", page=4)


@pytest.mark.asyncio
async def test_fake_provider_rejects_invalid_structured_output() -> None:
    provider = FakeLLMProvider(structured_payload={"date": "2026-11-13"})

    with pytest.raises(ValidationError):
        await provider.structured([], ExtractedDeadline)
