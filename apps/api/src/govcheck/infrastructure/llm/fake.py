from collections.abc import AsyncIterator, Sequence
from typing import Any

from govcheck.domain.llm import ChatMessage, LLMResult, StructuredModel


class FakeLLMProvider:
    def __init__(
        self,
        *,
        text: str = "",
        model: str = "fake",
        chunks: Sequence[str] | None = None,
        structured_payload: dict[str, Any] | None = None,
    ) -> None:
        self._text = text
        self._model = model
        self._chunks = tuple(chunks) if chunks is not None else (text,)
        self._structured_payload = structured_payload or {}

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResult:
        del messages
        return LLMResult(text=self._text, model=self._model)

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        del messages
        for chunk in self._chunks:
            yield chunk

    async def structured(
        self, messages: Sequence[ChatMessage], schema: type[StructuredModel]
    ) -> StructuredModel:
        del messages
        return schema.model_validate(self._structured_payload)
