from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    status: Literal["uploaded", "indexed", "failed"]
    created_at: datetime
    expires_at: datetime


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class CitationResponse(BaseModel):
    page_number: int
    excerpt: str
    chunk_id: UUID


class ChatAnswerResponse(BaseModel):
    text: str = Field(description="Model interpretation constrained by retrieved PDF evidence.")
    citations: list[CitationResponse]
    confidence: float
    grounded: bool


class AnalysisJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime


class FindingCitationResponse(BaseModel):
    chunk_id: UUID | None
    page_number: int
    excerpt: str = Field(description="Verbatim fact excerpt extracted from the uploaded PDF.")


class FindingResponse(BaseModel):
    id: UUID
    category: str
    title: str
    value: str = Field(description="Model interpretation, not a final legal determination.")
    evidence_status: Literal["supported", "unsupported", "conflicting"]
    confidence: float
    citations: list[FindingCitationResponse]
