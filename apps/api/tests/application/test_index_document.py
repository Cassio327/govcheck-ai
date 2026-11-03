from collections.abc import Sequence
from uuid import uuid4

import pytest

from govcheck.application.index_document import EmbeddingCardinalityError, IndexDocument
from govcheck.domain.documents import Chunk, Page
from govcheck.infrastructure.embeddings.fake import FakeEmbeddingProvider


class IndexDocumentRepository:
    def __init__(self, pages: Sequence[Page]) -> None:
        self._pages = list(pages)
        self.chunks: list[Chunk] = []

    async def list_pages(self, document_id):
        return [page for page in self._pages if page.document_id == document_id]

    async def add_chunks(self, chunks: Sequence[Chunk]) -> None:
        self.chunks.extend(chunks)


class IndexUnitOfWork:
    def __init__(self, repository: IndexDocumentRepository) -> None:
        self.documents = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_index_document_stores_one_embedding_per_non_empty_chunk() -> None:
    document_id = uuid4()
    repository = IndexDocumentRepository(
        [
            Page(document_id=document_id, number=1, text="prazo final em treze dias"),
            Page(document_id=document_id, number=2, text=""),
            Page(document_id=document_id, number=3, text="documento obrigatório"),
        ]
    )
    unit_of_work = IndexUnitOfWork(repository)
    service = IndexDocument(
        unit_of_work_factory=lambda: unit_of_work,
        embedding_provider=FakeEmbeddingProvider(dimension=4),
        target_chars=1_200,
        overlap_chars=180,
    )

    indexed = await service.execute(document_id)

    assert indexed == 2
    assert len(repository.chunks) == 2
    assert [chunk.page_number for chunk in repository.chunks] == [1, 3]
    assert all(len(chunk.embedding) == 4 for chunk in repository.chunks)
    assert unit_of_work.committed is True


@pytest.mark.asyncio
async def test_index_document_rejects_embedding_count_mismatch() -> None:
    document_id = uuid4()
    repository = IndexDocumentRepository(
        [Page(document_id=document_id, number=1, text="prazo final")]
    )
    unit_of_work = IndexUnitOfWork(repository)
    provider = FakeEmbeddingProvider(dimension=4, forced_vectors=[])
    service = IndexDocument(
        unit_of_work_factory=lambda: unit_of_work,
        embedding_provider=provider,
    )

    with pytest.raises(EmbeddingCardinalityError, match="1 chunks but 0 embeddings"):
        await service.execute(document_id)

    assert repository.chunks == []
    assert unit_of_work.committed is False
