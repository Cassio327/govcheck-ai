from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Document(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: str
    filename: str
    status: Literal["uploaded", "indexed", "failed"] = "uploaded"
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class Page(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    number: int = Field(ge=1)
    text: str


class Chunk(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    page_number: int = Field(ge=1)
    ordinal: int = Field(ge=0)
    text: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    embedding: list[float]


class AnalysisJob(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    session_id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=utc_now)
