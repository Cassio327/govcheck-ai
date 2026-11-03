from collections.abc import Sequence
from uuid import uuid4

import pytest

from govcheck.domain.documents import Chunk
from govcheck.infrastructure.retrieval.hybrid import HybridRetriever


class StubEmbeddingProvider:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector
        self.calls = 0

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return [self.vector.copy() for _ in texts]


class ChunkRepository:
    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self.chunks = list(chunks)
        self.requested_document_ids = []

    async def list_chunks(self, document_id):
        self.requested_document_ids.append(document_id)
        return [chunk for chunk in self.chunks if chunk.document_id == document_id]


class RetrievalUnitOfWork:
    def __init__(self, repository: ChunkRepository) -> None:
        self.documents = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


def make_chunk(document_id, *, ordinal, page, text, embedding) -> Chunk:
    return Chunk(
        document_id=document_id,
        page_number=page,
        ordinal=ordinal,
        text=text,
        start_char=0,
        end_char=len(text),
        embedding=embedding,
    )


@pytest.mark.asyncio
async def test_hybrid_search_fuses_vector_and_bm25_with_citations() -> None:
    document_id = uuid4()
    best = make_chunk(
        document_id,
        ordinal=0,
        page=4,
        text="O prazo para envio das propostas termina na sexta-feira.",
        embedding=[1.0, 0.0],
    )
    repository = ChunkRepository(
        [
            best,
            make_chunk(
                document_id,
                ordinal=1,
                page=7,
                text="Os documentos de habilitação são obrigatórios.",
                embedding=[0.0, 1.0],
            ),
            make_chunk(
                document_id,
                ordinal=2,
                page=9,
                text="O prazo de pagamento é de trinta dias.",
                embedding=[0.8, 0.2],
            ),
        ]
    )
    provider = StubEmbeddingProvider([1.0, 0.0])
    retriever = HybridRetriever(
        unit_of_work_factory=lambda: RetrievalUnitOfWork(repository),
        embedding_provider=provider,
    )

    evidence = await retriever.search(document_id, "prazo das propostas", limit=2)

    assert len(evidence) == 2
    assert evidence[0].chunk_id == best.id
    assert evidence[0].document_id == document_id
    assert evidence[0].page_number == 4
    assert "sexta-feira" in evidence[0].excerpt
    assert evidence[0].score >= evidence[1].score
    assert repository.requested_document_ids == [document_id]
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_hybrid_search_breaks_equal_scores_by_chunk_ordinal() -> None:
    document_id = uuid4()
    later = make_chunk(
        document_id,
        ordinal=1,
        page=2,
        text="conteúdo sem a expressão buscada",
        embedding=[1.0, 0.0],
    )
    earlier = make_chunk(
        document_id,
        ordinal=0,
        page=1,
        text="outro conteúdo sem correspondência",
        embedding=[1.0, 0.0],
    )
    repository = ChunkRepository([later, earlier])
    retriever = HybridRetriever(
        unit_of_work_factory=lambda: RetrievalUnitOfWork(repository),
        embedding_provider=StubEmbeddingProvider([1.0, 0.0]),
    )

    evidence = await retriever.search(document_id, "xilofone", limit=2)

    assert [item.chunk_id for item in evidence] == [earlier.id, later.id]


@pytest.mark.asyncio
async def test_hybrid_search_does_not_embed_an_empty_index() -> None:
    provider = StubEmbeddingProvider([1.0, 0.0])
    repository = ChunkRepository([])
    retriever = HybridRetriever(
        unit_of_work_factory=lambda: RetrievalUnitOfWork(repository),
        embedding_provider=provider,
    )

    assert await retriever.search(uuid4(), "prazo") == []
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_hybrid_search_bounds_long_excerpts() -> None:
    document_id = uuid4()
    repository = ChunkRepository(
        [
            make_chunk(
                document_id,
                ordinal=0,
                page=1,
                text="prazo " + ("muito longo " * 80),
                embedding=[1.0, 0.0],
            )
        ]
    )
    retriever = HybridRetriever(
        unit_of_work_factory=lambda: RetrievalUnitOfWork(repository),
        embedding_provider=StubEmbeddingProvider([1.0, 0.0]),
        excerpt_chars=120,
    )

    evidence = await retriever.search(document_id, "prazo")

    assert len(evidence[0].excerpt) <= 120
    assert evidence[0].excerpt.endswith("…")
