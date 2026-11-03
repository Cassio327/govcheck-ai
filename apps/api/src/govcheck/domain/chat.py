from typing import Literal
from uuid import UUID

from pydantic import Field

from govcheck.domain.documents import DomainModel


class Citation(DomainModel):
    page_number: int = Field(ge=1)
    excerpt: str
    chunk_id: UUID


class ChatAnswer(DomainModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    grounded: bool


class ChatDelta(DomainModel):
    type: Literal["text", "done"]
    text: str | None = None
    answer: ChatAnswer | None = None
