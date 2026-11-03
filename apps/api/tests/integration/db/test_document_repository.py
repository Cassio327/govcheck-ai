from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from govcheck.domain.documents import AnalysisJob, Chunk, Document, Page
from govcheck.domain.findings import Citation, Finding
from govcheck.infrastructure.db.base import Base
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork


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
async def test_document_repository_isolates_documents_pages_and_chunks_by_session(
    session_factory,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    document_a = Document(session_id="session-a", filename="edital-a.pdf", expires_at=expires_at)
    document_b = Document(session_id="session-b", filename="edital-b.pdf", expires_at=expires_at)
    page_a = Page(document_id=document_a.id, number=1, text="Prazo A")
    page_b = Page(document_id=document_b.id, number=1, text="Prazo B")
    chunk_a = Chunk(
        document_id=document_a.id,
        page_number=1,
        ordinal=0,
        text="Prazo A",
        start_char=0,
        end_char=7,
        embedding=[0.1] * 384,
    )

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        await unit_of_work.documents.add(document_a, [page_a])
        await unit_of_work.documents.add(document_b, [page_b])
        await unit_of_work.documents.add_chunks([chunk_a])
        await unit_of_work.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        loaded = await unit_of_work.documents.get_owned(document_a.id, "session-a")
        forbidden = await unit_of_work.documents.get_owned(document_a.id, "session-b")
        pages = await unit_of_work.documents.list_pages(document_a.id)
        chunks = await unit_of_work.documents.list_chunks(document_a.id)

    assert loaded == document_a
    assert forbidden is None
    assert pages == [page_a]
    assert chunks == [chunk_a]


@pytest.mark.asyncio
async def test_finding_repository_round_trips_typed_citations(session_factory) -> None:
    document = Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    finding = Finding(
        document_id=document.id,
        category="deadline",
        title="Prazo para propostas",
        value="13/11/2026",
        evidence_status="supported",
        confidence=0.94,
        citations=[Citation(page_number=4, excerpt="até 13 de novembro de 2026")],
    )

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        await unit_of_work.documents.add(document, [])
        await unit_of_work.findings.replace_for_document(document.id, [finding])
        await unit_of_work.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        loaded = await unit_of_work.findings.list_for_document(document.id)

    assert loaded == [finding]


@pytest.mark.asyncio
async def test_event_repository_assigns_monotonic_sequence_per_job(session_factory) -> None:
    document = Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    job = AnalysisJob(document_id=document.id, session_id="session-a")

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        await unit_of_work.documents.add(document, [])
        await unit_of_work.events.add_job(job)
        first = await unit_of_work.events.append(job.id, "analysis.started", {"step": 1})
        second = await unit_of_work.events.append(job.id, "analysis.completed", {"step": 2})
        await unit_of_work.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        replay = await unit_of_work.events.list_after(job.id, sequence=1)

    assert first.sequence == 1
    assert second.sequence == 2
    assert replay == [second]
