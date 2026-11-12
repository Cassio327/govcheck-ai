from collections.abc import AsyncIterator, Sequence
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    model: str
    usage: TokenUsage | None = None


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot produce a valid response."""


class LLMProvider(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResult: ...

    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...

    async def structured(
        self, messages: Sequence[ChatMessage], schema: type[StructuredModel]
    ) -> StructuredModel: ...
