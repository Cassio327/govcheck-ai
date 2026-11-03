from collections.abc import Callable
from datetime import timedelta

from govcheck.domain.documents import Document, Page, utc_now
from govcheck.domain.ingestion import PdfPolicy
from govcheck.domain.repositories import UnitOfWork
from govcheck.infrastructure.pdf.extractor import PdfExtractor


class IngestDocument:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        extractor: PdfExtractor,
        policy: PdfPolicy,
        retention_minutes: int,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._extractor = extractor
        self._policy = policy
        self._retention_minutes = retention_minutes

    async def execute(
        self,
        session_id: str,
        filename: str,
        content: bytes,
    ) -> Document:
        extracted_pages = self._extractor.extract(content, self._policy)
        document = Document(
            session_id=session_id,
            filename=filename,
            expires_at=utc_now() + timedelta(minutes=self._retention_minutes),
        )
        pages = [
            Page(document_id=document.id, number=page.number, text=page.text)
            for page in extracted_pages
        ]
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.documents.add(document, pages)
            await unit_of_work.commit()
        return document
