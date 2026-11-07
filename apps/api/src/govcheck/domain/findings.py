from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field

from govcheck.domain.analysis import FindingCategory
from govcheck.domain.documents import DomainModel, utc_now

EvidenceStatus = Literal["supported", "unsupported", "conflicting"]


class Citation(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    page_number: int = Field(ge=1)
    excerpt: str
    chunk_id: UUID | None = None


class Finding(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    category: FindingCategory
    title: str
    value: str
    evidence_status: EvidenceStatus
    confidence: float = Field(ge=0, le=1)
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ToolRun(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    name: str
    status: Literal["verified", "not_found", "unavailable", "invalid"]
    source_url: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None


class Report(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    markdown: str
    json_payload: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)
