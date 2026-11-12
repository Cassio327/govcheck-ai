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
    """Provider failure with safe-to-log diagnostics (never raw provider bodies)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class LLMProvider(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResult: ...

    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...

    async def structured(
        self, messages: Sequence[ChatMessage], schema: type[StructuredModel]
    ) -> StructuredModel: ...
