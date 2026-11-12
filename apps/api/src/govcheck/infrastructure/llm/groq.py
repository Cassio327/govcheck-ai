import json
from collections.abc import AsyncIterator, Sequence

import httpx
from pydantic import SecretStr

from govcheck.domain.llm import (
    ChatMessage,
    LLMProviderError,
    LLMResult,
    StructuredModel,
    TokenUsage,
)


class GroqLLMProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        base_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = client

    @property
    def client_created(self) -> bool:
        return self._client is not None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{self._base_url}/",
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                timeout=httpx.Timeout(45.0),
            )
        return self._client

    @staticmethod
    def _messages(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": item.role, "content": item.content} for item in messages]

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResult:
        try:
            response = await self._get_client().post(
                "chat/completions",
                json={"model": self._model, "messages": self._messages(messages), "temperature": 0},
            )
            response.raise_for_status()
            payload = response.json()
            usage = payload.get("usage")
            return LLMResult(
                text=payload["choices"][0]["message"]["content"],
                model=payload.get("model", self._model),
                usage=TokenUsage.model_validate(usage) if usage else None,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMProviderError("Groq request failed") from error

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        try:
            async with self._get_client().stream(
                "POST",
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": self._messages(messages),
                    "temperature": 0,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    payload = json.loads(line.removeprefix("data: "))
                    content = payload["choices"][0]["delta"].get("content")
                    if content:
                        yield content
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMProviderError("Groq streaming request failed") from error

    async def structured(
        self, messages: Sequence[ChatMessage], schema: type[StructuredModel]
    ) -> StructuredModel:
        schema_instruction = ChatMessage(
            role="system",
            content=(
                "Return only a JSON object matching this JSON Schema: "
                f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
            ),
        )
        try:
            response = await self._get_client().post(
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": self._messages([schema_instruction, *messages]),
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return schema.model_validate_json(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMProviderError("Groq structured request failed") from error
