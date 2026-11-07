from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from govcheck.domain.documents import AnalysisJob, Chunk, Document, Page
from govcheck.domain.events import StreamEvent
from govcheck.domain.findings import Citation, Finding
from govcheck.infrastructure.db.models import (
    AnalysisJobRecord,
    ChunkRecord,
    CitationRecord,
    DocumentRecord,
    FindingRecord,
    PageRecord,
    StreamEventRecord,
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document, pages: Sequence[Page]) -> None:
        self._session.add(
            DocumentRecord(
                id=document.id,
                session_id=document.session_id,
                filename=document.filename,
                status=document.status,
                created_at=document.created_at,
                expires_at=document.expires_at,
            )
        )
        self._session.add_all(
            PageRecord(id=page.id, document_id=page.document_id, number=page.number, text=page.text)
            for page in pages
        )

    async def get_owned(self, document_id: UUID, session_id: str) -> Document | None:
        record = await self._session.scalar(
            select(DocumentRecord).where(
                DocumentRecord.id == document_id,
                DocumentRecord.session_id == session_id,
            )
        )
        if record is None:
            return None
        return Document(
            id=record.id,
            session_id=record.session_id,
            filename=record.filename,
            status=record.status,
            created_at=_aware(record.created_at),
            expires_at=_aware(record.expires_at),
        )

    async def list_pages(self, document_id: UUID) -> list[Page]:
        records = (
            await self._session.scalars(
                select(PageRecord)
                .where(PageRecord.document_id == document_id)
                .order_by(PageRecord.number)
            )
        ).all()
        return [
            Page(id=item.id, document_id=item.document_id, number=item.number, text=item.text)
            for item in records
        ]

    async def add_chunks(self, chunks: Sequence[Chunk]) -> None:
        self._session.add_all(
            ChunkRecord(
                id=chunk.id,
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                ordinal=chunk.ordinal,
                text=chunk.text,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                embedding=chunk.embedding,
            )
            for chunk in chunks
        )

    async def list_chunks(self, document_id: UUID) -> list[Chunk]:
        records = (
            await self._session.scalars(
                select(ChunkRecord)
                .where(ChunkRecord.document_id == document_id)
                .order_by(ChunkRecord.ordinal)
            )
        ).all()
        return [
            Chunk(
                id=item.id,
                document_id=item.document_id,
                page_number=item.page_number,
                ordinal=item.ordinal,
                text=item.text,
                start_char=item.start_char,
                end_char=item.end_char,
                embedding=list(item.embedding),
            )
            for item in records
        ]


class SqlAlchemyFindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_document(self, document_id: UUID, findings: Sequence[Finding]) -> None:
        existing_ids = select(FindingRecord.id).where(FindingRecord.document_id == document_id)
        await self._session.execute(
            delete(CitationRecord).where(CitationRecord.finding_id.in_(existing_ids))
        )
        await self._session.execute(
            delete(FindingRecord).where(FindingRecord.document_id == document_id)
        )
        for finding in findings:
            record = FindingRecord(
                id=finding.id,
                document_id=finding.document_id,
                category=finding.category.value,
                title=finding.title,
                value=finding.value,
                evidence_status=finding.evidence_status,
                confidence=finding.confidence,
                created_at=finding.created_at,
            )
            record.citations = [
                CitationRecord(
                    id=citation.id,
                    finding_id=finding.id,
                    chunk_id=citation.chunk_id,
                    page_number=citation.page_number,
                    excerpt=citation.excerpt,
                )
                for citation in finding.citations
            ]
            self._session.add(record)

    async def list_for_document(self, document_id: UUID) -> list[Finding]:
        records = (
            await self._session.scalars(
                select(FindingRecord)
                .options(selectinload(FindingRecord.citations))
                .where(FindingRecord.document_id == document_id)
                .order_by(FindingRecord.created_at, FindingRecord.id)
            )
        ).all()
        return [
            Finding(
                id=record.id,
                document_id=record.document_id,
                category=record.category,
                title=record.title,
                value=record.value,
                evidence_status=record.evidence_status,
                confidence=record.confidence,
                created_at=_aware(record.created_at),
                citations=[
                    Citation(
                        id=citation.id,
                        chunk_id=citation.chunk_id,
                        page_number=citation.page_number,
                        excerpt=citation.excerpt,
                    )
                    for citation in record.citations
                ],
            )
            for record in records
        ]


class SqlAlchemyEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_job(self, job: AnalysisJob) -> None:
        self._session.add(
            AnalysisJobRecord(
                id=job.id,
                document_id=job.document_id,
                session_id=job.session_id,
                status=job.status,
                created_at=job.created_at,
            )
        )

    async def update_job_status(self, job_id: UUID, status: str) -> None:
        await self._session.execute(
            update(AnalysisJobRecord).where(AnalysisJobRecord.id == job_id).values(status=status)
        )

    async def append(self, job_id: UUID, event_type: str, payload: dict[str, Any]) -> StreamEvent:
        current = await self._session.scalar(
            select(func.max(StreamEventRecord.sequence)).where(StreamEventRecord.job_id == job_id)
        )
        event = StreamEvent(
            job_id=job_id,
            sequence=(current or 0) + 1,
            event_type=event_type,
            payload=payload,
        )
        self._session.add(
            StreamEventRecord(
                id=event.id,
                job_id=event.job_id,
                sequence=event.sequence,
                event_type=event.event_type,
                payload=event.payload,
                created_at=event.created_at,
            )
        )
        await self._session.flush()
        return event

    async def list_after(self, job_id: UUID, sequence: int) -> list[StreamEvent]:
        records = (
            await self._session.scalars(
                select(StreamEventRecord)
                .where(
                    StreamEventRecord.job_id == job_id,
                    StreamEventRecord.sequence > sequence,
                )
                .order_by(StreamEventRecord.sequence)
            )
        ).all()
        return [
            StreamEvent(
                id=record.id,
                job_id=record.job_id,
                sequence=record.sequence,
                event_type=record.event_type,
                payload=record.payload,
                created_at=_aware(record.created_at),
            )
            for record in records
        ]
