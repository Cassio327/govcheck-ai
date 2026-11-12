from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from govcheck.domain.documents import DomainModel


class FindingCategory(StrEnum):
    DEADLINE = "deadline"
    DOCUMENT = "document"
    VALUE = "value"
    CRITERION = "criterion"
    SANCTION = "sanction"
    OBLIGATION = "obligation"


class FindingDraft(DomainModel):
    category: FindingCategory
    title: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=2_000)
    citation_ids: list[UUID] = Field(default_factory=list, max_length=6)
    confidence: float = Field(ge=0, le=1)
    external_identifier: str | None = Field(default=None, max_length=64)


class ExternalValidation(DomainModel):
    status: Literal["verified", "not_found", "unavailable", "invalid"]
    matches: bool | None = None
    source_url: str | None = None
    data: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None


class ToolRegistryPort(Protocol):
    async def validate_identifier(
        self,
        identifier: str,
        *,
        document_id: UUID | None = None,
    ) -> ExternalValidation: ...


class UnavailableToolRegistry:
    """Safe default until an allowlisted public-data adapter is configured."""

    async def validate_identifier(
        self,
        identifier: str,
        *,
        document_id: UUID | None = None,
    ) -> ExternalValidation:
        del identifier
        del document_id
        return ExternalValidation(
            status="unavailable",
            error_code="tool_not_configured",
        )
