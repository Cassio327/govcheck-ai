from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: UUID
    document_id: UUID
    page_number: int
    excerpt: str
    score: float


class EvidenceRetriever(Protocol):
    async def search(
        self,
        document_id: UUID,
        query: str,
        limit: int = 8,
    ) -> Sequence[Evidence]: ...


class RetrieveEvidence:
    def __init__(self, retriever: EvidenceRetriever) -> None:
        self._retriever = retriever

    async def execute(
        self,
        document_id: UUID,
        query: str,
        *,
        limit: int = 8,
    ) -> list[Evidence]:
        if not query.strip() or limit <= 0:
            return []
        return list(await self._retriever.search(document_id, query.strip(), limit))
