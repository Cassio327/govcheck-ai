from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from govcheck.domain.documents import utc_now


class ToolRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["verified", "not_found", "unavailable", "invalid"]
    source_url: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None


class Tool(Protocol):
    name: str

    async def execute(self, arguments: Mapping[str, Any]) -> ToolResult: ...

    def sanitize_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]: ...
