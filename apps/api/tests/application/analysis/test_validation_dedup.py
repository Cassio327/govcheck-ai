from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from govcheck.application.analysis.graph import AnalysisDependencies, RunAnalysis
from govcheck.application.analysis.nodes import ExternalValidation
from govcheck.application.retrieve_evidence import Evidence
from govcheck.domain.documents import Document

from .test_graph import MemoryUnitOfWork, SchemaProvider, StubRetriever, StubToolRegistry


@pytest.mark.asyncio
async def test_repeated_pncp_identifier_is_checked_only_once_per_analysis() -> None:
    document = Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    chunk_id = uuid4()
    identifier = "00394460000141-1-000001/2021"
    registry = StubToolRegistry(ExternalValidation(status="verified", matches=True))
    unit_of_work = MemoryUnitOfWork(document)
    runner = RunAnalysis(
        AnalysisDependencies(
            unit_of_work_factory=lambda: unit_of_work,
            retriever=StubRetriever(
                [Evidence(chunk_id, document.id, 1, f"Registro PNCP {identifier}", 0.03)]
            ),
            llm_provider=SchemaProvider(
                extraction={
                    "findings": [
                        {
                            "category": category,
                            "title": "Referência PNCP",
                            "value": identifier,
                            "external_identifier": identifier,
                            "citation_ids": [str(chunk_id)],
                            "confidence": 0.9,
                        }
                        for category in ("document", "obligation")
                    ]
                },
                critique={
                    "decisions": [
                        {"draft_index": index, "supported": True, "confidence": 0.9}
                        for index in range(2)
                    ]
                },
            ),
            tool_registry=registry,
        )
    )

    job = await runner.execute("session-a", document.id)

    assert registry.calls == [identifier]
    assert len(unit_of_work.findings.items) == 2
    event = next(
        event
        for event in unit_of_work.events.events
        if event.job_id == job.id and event.event_type == "analysis.external_validation.completed"
    )
    assert event.payload["validation_count"] == 2
    assert event.payload["external_requests"] == 1
    assert event.payload["validation_status_counts"]["verified"] == 2
