from collections.abc import Sequence

import pytest

from govcheck.application.ingest_document import IngestDocument
from govcheck.domain.documents import Document, Page
from govcheck.domain.ingestion import IngestionError, PdfPolicy
from govcheck.infrastructure.pdf.extractor import PdfExtractor
from tests.fixtures.pdf_factory import make_text_pdf


class RecordingDocumentRepository:
    def __init__(self) -> None:
        self.document: Document | None = None
        self.pages: list[Page] = []

    async def add(self, document: Document, pages: Sequence[Page]) -> None:
        self.document = document
        self.pages = list(pages)


class RecordingUnitOfWork:
    def __init__(self) -> None:
        self.documents = RecordingDocumentRepository()
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_ingest_document_persists_extracted_pages_transactionally() -> None:
    unit_of_work = RecordingUnitOfWork()
    service = IngestDocument(
        unit_of_work_factory=lambda: unit_of_work,
        extractor=PdfExtractor(),
        policy=PdfPolicy(max_bytes=1_000_000, max_pages=50),
        retention_minutes=60,
    )

    document = await service.execute(
        session_id="session-a",
        filename="edital.pdf",
        content=make_text_pdf(["Primeira página", "Segunda página"]),
    )

    assert document.session_id == "session-a"
    assert document.filename == "edital.pdf"
    assert [page.number for page in unit_of_work.documents.pages] == [1, 2]
    assert all(page.document_id == document.id for page in unit_of_work.documents.pages)
    assert unit_of_work.committed is True


@pytest.mark.asyncio
async def test_ingest_document_does_not_open_transaction_for_invalid_pdf() -> None:
    factory_calls = 0

    def factory() -> RecordingUnitOfWork:
        nonlocal factory_calls
        factory_calls += 1
        return RecordingUnitOfWork()

    service = IngestDocument(
        unit_of_work_factory=factory,
        extractor=PdfExtractor(),
        policy=PdfPolicy(max_bytes=1_000_000, max_pages=50),
        retention_minutes=60,
    )

    with pytest.raises(IngestionError, match="PDF"):
        await service.execute("session-a", "corrupt.pdf", b"not-a-pdf")

    assert factory_calls == 0
