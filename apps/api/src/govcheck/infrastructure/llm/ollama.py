import json
from collections.abc import AsyncIterator, Sequence

import httpx

from govcheck.domain.llm import (
    ChatMessage,
    LLMProviderError,
    LLMResult,
    StructuredModel,
    TokenUsage,
)


class OllamaLLMProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client

    @property
    def client_created(self) -> bool:
        return self._client is not None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{self._base_url}/",
                timeout=httpx.Timeout(120.0),
            )
        return self._client

    @staticmethod
    def _messages(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": item.role, "content": item.content} for item in messages]

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResult:
        try:
            response = await self._get_client().post(
                "api/chat",
                json={"model": self._model, "messages": self._messages(messages), "stream": False},
            )
            response.raise_for_status()
            payload = response.json()
            usage = None
            if "prompt_eval_count" in payload and "eval_count" in payload:
                usage = TokenUsage(
                    prompt_tokens=payload["prompt_eval_count"],
                    completion_tokens=payload["eval_count"],
                    total_tokens=payload["prompt_eval_count"] + payload["eval_count"],
                )
            return LLMResult(text=payload["message"]["content"], model=self._model, usage=usage)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMProviderError("Ollama request failed") from error

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        try:
            async with self._get_client().stream(
                "POST",
                "api/chat",
                json={"model": self._model, "messages": self._messages(messages), "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    content = payload.get("message", {}).get("content")
                    if content:
                        yield content
        except (httpx.HTTPError, TypeError, ValueError) as error:
            raise LLMProviderError("Ollama streaming request failed") from error

    async def structured(
        self, messages: Sequence[ChatMessage], schema: type[StructuredModel]
    ) -> StructuredModel:
        try:
            response = await self._get_client().post(
                "api/chat",
                json={
                    "model": self._model,
                    "messages": self._messages(messages),
                    "stream": False,
                    "format": schema.model_json_schema(),
                },
            )
            response.raise_for_status()
            return schema.model_validate_json(response.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMProviderError("Ollama structured request failed") from error
