import re
from collections.abc import AsyncIterator, Sequence

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from govcheck.api.dependencies import AppServices, get_services
from govcheck.application.analysis.graph import AnalysisDependencies, RunAnalysis
from govcheck.application.chat_with_document import ChatWithDocument
from govcheck.application.index_document import IndexDocument
from govcheck.application.ingest_document import IngestDocument
from govcheck.application.render_report import RenderReport
from govcheck.domain.analysis import UnavailableToolRegistry
from govcheck.domain.ingestion import PdfPolicy
from govcheck.domain.llm import ChatMessage, LLMResult
from govcheck.infrastructure.db.base import Base
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork
from govcheck.infrastructure.embeddings.fake import FakeEmbeddingProvider
from govcheck.infrastructure.pdf.extractor import PdfExtractor
from govcheck.infrastructure.retrieval.hybrid import HybridRetriever
from govcheck.main import app


class DeterministicAPIProvider:
    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResult:
        return LLMResult(text="Resposta determinística", model="api-test")

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        yield "Resposta determinística"

    async def structured(self, messages, schema):
        prompt = messages[-1].content
        source_ids = re.findall(r'<source id="([0-9a-f-]+)"', prompt)
        if schema.__name__ == "GroundedLLMAnswer":
            return schema.model_validate(
                {
                    "answer": "O prazo indicado no edital é 13 de novembro.",
                    "citation_ids": source_ids[:1],
                    "confidence": 0.9,
                }
            )
        if schema.__name__ == "ExtractedFindings":
            return schema.model_validate(
                {
                    "findings": [
                        {
                            "category": "deadline",
                            "title": "Prazo para propostas",
                            "value": "13 de novembro",
                            "citation_ids": source_ids[:1],
                            "confidence": 0.88,
                        }
                    ]
                }
            )
        if schema.__name__ == "CriticDecisions":
            indexes = [int(value) for value in re.findall(r'<claim index="(\d+)"', prompt)]
            return schema.model_validate(
                {
                    "decisions": [
                        {"draft_index": index, "supported": True, "confidence": 0.86}
                        for index in indexes
                    ]
                }
            )
        raise AssertionError(f"Unexpected schema: {schema.__name__}")


@pytest_asyncio.fixture
async def api_services():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    embedding_provider = FakeEmbeddingProvider(dimension=384)
    retriever = HybridRetriever(
        unit_of_work_factory=unit_of_work_factory,
        embedding_provider=embedding_provider,
    )
    llm_provider = DeterministicAPIProvider()
    services = AppServices(
        unit_of_work_factory=unit_of_work_factory,
        ingest_document=IngestDocument(
            unit_of_work_factory=unit_of_work_factory,
            extractor=PdfExtractor(),
            policy=PdfPolicy(max_bytes=5_242_880, max_pages=50),
            retention_minutes=60,
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
                tool_registry=UnavailableToolRegistry(),
            )
        ),
        report=RenderReport(unit_of_work_factory=unit_of_work_factory),
    )
    yield services
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(api_services):
    app.dependency_overrides[get_services] = lambda: api_services
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
