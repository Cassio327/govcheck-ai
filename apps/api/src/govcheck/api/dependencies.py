from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Header

from govcheck.api.errors import APIError
from govcheck.application.analysis.graph import AnalysisDependencies, RunAnalysis
from govcheck.application.chat_with_document import ChatWithDocument
from govcheck.application.index_document import IndexDocument
from govcheck.application.ingest_document import IngestDocument
from govcheck.application.render_report import RenderReport
from govcheck.config import get_settings
from govcheck.domain.ingestion import PdfPolicy
from govcheck.domain.repositories import UnitOfWork
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork, build_session_factory
from govcheck.infrastructure.embeddings.factory import build_embedding_provider
from govcheck.infrastructure.llm.factory import build_llm_provider
from govcheck.infrastructure.pdf.extractor import PdfExtractor
from govcheck.infrastructure.retrieval.hybrid import HybridRetriever
from govcheck.infrastructure.tools.procurement_lookup import ProcurementLookupTool
from govcheck.infrastructure.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class AppServices:
    unit_of_work_factory: Callable[[], UnitOfWork]
    ingest_document: IngestDocument
    index_document: IndexDocument
    chat: ChatWithDocument
    analysis: RunAnalysis
    report: RenderReport
    max_upload_bytes: int = 5_242_880


@lru_cache
def get_services() -> AppServices:
    settings = get_settings()
    if not settings.database_url:
        raise APIError(503, "service_not_ready", "O banco de dados não está configurado.")
    session_factory = build_session_factory(settings.database_url)

    def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    embedding_provider = build_embedding_provider(settings)
    llm_provider = build_llm_provider(settings)
    retriever = HybridRetriever(
        unit_of_work_factory=unit_of_work_factory,
        embedding_provider=embedding_provider,
    )
    tool_registry = ToolRegistry(
        [ProcurementLookupTool()],
        unit_of_work_factory=unit_of_work_factory,
    )
    return AppServices(
        unit_of_work_factory=unit_of_work_factory,
        ingest_document=IngestDocument(
            unit_of_work_factory=unit_of_work_factory,
            extractor=PdfExtractor(),
            policy=PdfPolicy(
                max_bytes=settings.max_upload_bytes,
                max_pages=settings.max_pdf_pages,
            ),
            retention_minutes=settings.retention_minutes,
        ),
        index_document=IndexDocument(
            unit_of_work_factory=unit_of_work_factory,
            embedding_provider=embedding_provider,
        ),
        chat=ChatWithDocument(
            unit_of_work_factory=unit_of_work_factory,
            retriever=retriever,
            llm_provider=llm_provider,
        ),
        analysis=RunAnalysis(
            AnalysisDependencies(
                unit_of_work_factory=unit_of_work_factory,
                retriever=retriever,
                llm_provider=llm_provider,
                tool_registry=tool_registry,
            )
        ),
        report=RenderReport(unit_of_work_factory=unit_of_work_factory),
        max_upload_bytes=settings.max_upload_bytes,
    )


def get_session_id(
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> str:
    session_id = (x_session_id or "").strip()
    if not session_id or len(session_id) > 128:
        raise APIError(
            400,
            "session_required",
            "Envie um identificador de sessão válido no cabeçalho X-Session-ID.",
        )
    return session_id
