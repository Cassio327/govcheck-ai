import asyncio
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

    @staticmethod
    def _failure_code(status: int) -> str:
        if status in (401, 403):
            return "authentication"
        if status == 429:
            return "rate_limited"
        if status in (400, 422):
            return "invalid_request"
        if status >= 500:
            return "provider_unavailable"
        return "provider_http_error"

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after is not None:
            try:
                seconds = float(retry_after)
                if 0 <= seconds <= 60:
                    return max(0.5, seconds)
            except ValueError:
                pass
        return min(60.0, 2.0**attempt)

    async def _post_structured_with_retry(self, payload: dict[str, object]) -> httpx.Response:
        # Groq limits can be reached by cumulative tokens, not just request count.
        # Never log or return provider error bodies: they may contain prompt excerpts.
        for attempt in range(3):
            try:
                response = await self._get_client().post("chat/completions", json=payload)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                if status in (429, 500, 502, 503, 504) and attempt < 2:
                    delay = self._retry_delay(
                        error.response.headers.get("retry-after") if status == 429 else None,
                        attempt,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise LLMProviderError(
                    "Groq structured request failed",
                    code=self._failure_code(status),
                    status_code=status,
                ) from error
            except httpx.RequestError as error:
                if attempt < 2:
                    await asyncio.sleep(2.0**attempt)
                    continue
                raise LLMProviderError(
                    "Groq structured connection failed",
                    code="timeout" if isinstance(error, httpx.TimeoutException) else "connection",
                ) from error
        raise AssertionError("Groq retry loop exhausted")

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
        base_messages = self._messages([schema_instruction, *messages])
        payload: dict[str, object] = {
            "model": self._model,
            "messages": base_messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        # GPT-OSS supports low reasoning effort, reducing time and token pressure.
        if self._model in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
            payload["reasoning_effort"] = "low"

        for attempt in range(2):
            if attempt:
                payload["messages"] = [
                    base_messages[0],
                    {
                        "role": "system",
                        "content": (
                            "Follow the provided JSON Schema exactly. Output a single "
                            "JSON object, not prose or markdown. Do not invent citations."
                        ),
                    },
                    *base_messages[1:],
                ]
            response = await self._post_structured_with_retry(payload)
            try:
                content = response.json()["choices"][0]["message"]["content"]
                return schema.model_validate_json(content)
            except (KeyError, IndexError, TypeError, ValueError) as error:
                if attempt:
                    raise LLMProviderError(
                        "Groq output did not match the requested schema",
                        code="invalid_structured_output",
                    ) from error
        raise AssertionError("Groq structured retry loop exhausted")
