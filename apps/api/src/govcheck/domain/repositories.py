from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from govcheck.domain.documents import AnalysisJob, Chunk, Document, Page
from govcheck.domain.events import StreamEvent
from govcheck.domain.findings import Finding, ToolRun


class ActiveAnalysisConflict(RuntimeError):
    """Persistence rejected a second active job for one session."""


class DocumentRepository(Protocol):
    async def add(self, document: Document, pages: Sequence[Page]) -> None: ...

    async def get_owned(self, document_id: UUID, session_id: str) -> Document | None: ...

    async def update_status(self, document_id: UUID, status: str) -> None: ...

    async def delete_expired(self, before: datetime) -> int: ...

    async def list_pages(self, document_id: UUID) -> list[Page]: ...

    async def add_chunks(self, chunks: Sequence[Chunk]) -> None: ...

    async def list_chunks(self, document_id: UUID) -> list[Chunk]: ...


class FindingRepository(Protocol):
    async def replace_for_document(
        self, document_id: UUID, findings: Sequence[Finding]
    ) -> None: ...

    async def list_for_document(self, document_id: UUID) -> list[Finding]: ...


class EventRepository(Protocol):
    async def add_job(self, job: AnalysisJob) -> None: ...

    async def update_job_status(self, job_id: UUID, status: str) -> None: ...

    async def append(
        self, job_id: UUID, event_type: str, payload: dict[str, Any]
    ) -> StreamEvent: ...

    async def list_after(self, job_id: UUID, sequence: int) -> list[StreamEvent]: ...

    async def latest_job_for_document(
        self, document_id: UUID, session_id: str
    ) -> AnalysisJob | None: ...

    async def active_for_session(self, session_id: str) -> AnalysisJob | None: ...

    async def fail_stale_for_session(self, session_id: str, before: datetime) -> int: ...


class ToolRunRepository(Protocol):
    async def add(self, tool_run: ToolRun) -> None: ...

    async def list_for_document(self, document_id: UUID) -> list[ToolRun]: ...


class UnitOfWork(Protocol):
    documents: DocumentRepository
    findings: FindingRepository
    events: EventRepository
    tools: ToolRunRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
