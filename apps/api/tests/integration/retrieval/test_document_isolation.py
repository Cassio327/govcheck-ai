from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from govcheck.domain.documents import Chunk, Document
from govcheck.infrastructure.db.base import Base
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork
from govcheck.infrastructure.embeddings.fake import FakeEmbeddingProvider
from govcheck.infrastructure.retrieval.hybrid import HybridRetriever


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_retrieval_never_leaks_evidence_from_another_document(session_factory) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    document_a = Document(session_id="session-a", filename="a.pdf", expires_at=expires_at)
    document_b = Document(session_id="session-b", filename="b.pdf", expires_at=expires_at)
    vector = [1.0] + ([0.0] * 383)
    chunk_a = Chunk(
        document_id=document_a.id,
        page_number=1,
        ordinal=0,
        text="Prazo público do documento A.",
        start_char=0,
        end_char=30,
        embedding=vector,
    )
    chunk_b = Chunk(
        document_id=document_b.id,
        page_number=99,
        ordinal=0,
        text="Prazo SECRETO do documento B.",
        start_char=0,
        end_char=31,
        embedding=vector,
    )
    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        await unit_of_work.documents.add(document_a, [])
        await unit_of_work.documents.add(document_b, [])
        await unit_of_work.documents.add_chunks([chunk_a, chunk_b])
        await unit_of_work.commit()

    retriever = HybridRetriever(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        embedding_provider=FakeEmbeddingProvider(dimension=384, forced_vectors=[vector]),
    )

    evidence = await retriever.search(document_a.id, "prazo documento", limit=8)

    assert [item.chunk_id for item in evidence] == [chunk_a.id]
    assert all(item.document_id == document_a.id for item in evidence)
    assert all("SECRETO" not in item.excerpt for item in evidence)
