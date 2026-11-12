from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from govcheck.application import cleanup_expired
from govcheck.application.cleanup_expired import CleanupExpiredDocuments
from govcheck.domain.documents import AnalysisJob, Chunk, Document, Page, utc_now
from govcheck.domain.findings import Citation, Finding, ToolRun
from govcheck.infrastructure.db.base import Base
from govcheck.infrastructure.db.models import (
    AnalysisJobRecord,
    ChunkRecord,
    CitationRecord,
    DocumentRecord,
    FindingRecord,
    PageRecord,
    ReportRecord,
    StreamEventRecord,
    ToolRunRecord,
)
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork
from tests.fixtures.pdf_factory import make_text_pdf


@pytest_asyncio.fixture
async def retention_database():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_ingested_documents_expire_after_the_configured_60_minutes(api_services) -> None:
    before = utc_now()
    document = await api_services.ingest_document.execute(
        "retention-session",
        "edital.pdf",
        make_text_pdf(["Documento público para análise."]),
    )
    after = utc_now()

    assert before + timedelta(minutes=60) <= document.expires_at
    assert document.expires_at <= after + timedelta(minutes=60)


@pytest.mark.asyncio
async def test_expired_document_is_inaccessible_before_physical_cleanup(
    retention_database,
) -> None:
    expired = Document(
        session_id="expired-session",
        filename="expired.pdf",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    async with SqlAlchemyUnitOfWork(retention_database) as unit_of_work:
        await unit_of_work.documents.add(expired, [])
        await unit_of_work.commit()

    async with SqlAlchemyUnitOfWork(retention_database) as unit_of_work:
        loaded = await unit_of_work.documents.get_owned(expired.id, expired.session_id)

    assert loaded is None


@pytest.mark.asyncio
async def test_cleanup_removes_expired_document_content_and_keeps_fresh_data(
    retention_database,
) -> None:
    expired = Document(
        session_id="expired-session",
        filename="expired.pdf",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    fresh = Document(
        session_id="fresh-session",
        filename="fresh.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    expired_page = Page(document_id=expired.id, number=1, text="conteúdo expirado")
    fresh_page = Page(document_id=fresh.id, number=1, text="conteúdo atual")
    expired_chunk = Chunk(
        document_id=expired.id,
        page_number=1,
        ordinal=0,
        text="conteúdo expirado",
        start_char=0,
        end_char=18,
        embedding=[0.1] * 384,
    )
    fresh_chunk = Chunk(
        document_id=fresh.id,
        page_number=1,
        ordinal=0,
        text="conteúdo atual",
        start_char=0,
        end_char=14,
        embedding=[0.2] * 384,
    )
    expired_job = AnalysisJob(
        document_id=expired.id, session_id=expired.session_id, status="completed"
    )
    expired_finding = Finding(
        document_id=expired.id,
        category="deadline",
        title="Prazo expirado",
        value="13 de novembro",
        evidence_status="supported",
        confidence=0.9,
        citations=[
            Citation(
                chunk_id=expired_chunk.id,
                page_number=1,
                excerpt="conteúdo expirado",
            )
        ],
    )
    expired_tool_run = ToolRun(
        document_id=expired.id,
        name="pncp_procurement_lookup",
        status="verified",
        request={"identifier": "expired"},
        data={"private_snapshot": "expired"},
    )

    async with SqlAlchemyUnitOfWork(retention_database) as unit_of_work:
        await unit_of_work.documents.add(expired, [expired_page])
        await unit_of_work.documents.add(fresh, [fresh_page])
        await unit_of_work.documents.add_chunks([expired_chunk, fresh_chunk])
        await unit_of_work.events.add_job(expired_job)
        await unit_of_work.events.append(expired_job.id, "analysis.completed", {})
        await unit_of_work.findings.replace_for_document(expired.id, [expired_finding])
        await unit_of_work.tools.add(expired_tool_run)
        await unit_of_work.commit()
    async with retention_database() as session:
        session.add(
            ReportRecord(
                document_id=expired.id,
                markdown="relatório expirado",
                json_payload={"private_snapshot": "expired"},
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    cleanup = CleanupExpiredDocuments(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(retention_database)
    )
    deleted = await cleanup.execute()

    assert deleted == 1
    async with retention_database() as session:
        expired_counts = {
            model.__tablename__: await session.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.id == expired.id
                    if model is DocumentRecord
                    else model.document_id == expired.id
                )
            )
            for model in (
                DocumentRecord,
                PageRecord,
                ChunkRecord,
                AnalysisJobRecord,
                FindingRecord,
                ToolRunRecord,
                ReportRecord,
            )
        }
        citation_count = await session.scalar(select(func.count()).select_from(CitationRecord))
        event_count = await session.scalar(select(func.count()).select_from(StreamEventRecord))
    assert expired_counts == {
        "documents": 0,
        "pages": 0,
        "chunks": 0,
        "analysis_jobs": 0,
        "findings": 0,
        "tool_runs": 0,
        "reports": 0,
    }
    assert citation_count == 0
    assert event_count == 0

    async with SqlAlchemyUnitOfWork(retention_database) as unit_of_work:
        assert await unit_of_work.documents.get_owned(fresh.id, fresh.session_id) == fresh
        assert await unit_of_work.documents.list_pages(fresh.id) == [fresh_page]
        assert await unit_of_work.documents.list_chunks(fresh.id) == [fresh_chunk]


@pytest.mark.asyncio
async def test_cleanup_database_entrypoint_deletes_expired_rows(tmp_path) -> None:
    database_path = tmp_path / "cleanup.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    expired = Document(
        session_id="cleanup-command",
        filename="expired.pdf",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        await unit_of_work.documents.add(expired, [])
        await unit_of_work.commit()
    await engine.dispose()

    assert hasattr(cleanup_expired, "cleanup_database")
    deleted = await cleanup_expired.cleanup_database(database_url)

    assert deleted == 1
