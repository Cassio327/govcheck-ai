from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from govcheck.application.analysis.graph import AnalysisDependencies, RunAnalysis
from govcheck.application.analysis.nodes import ExternalValidation
from govcheck.application.retrieve_evidence import Evidence
from govcheck.domain.documents import Document

from .test_graph import MemoryUnitOfWork, SchemaProvider, StubRetriever, StubToolRegistry


def make_document():
    return Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_critic_marks_unknown_citation_unsupported_without_substitution() -> None:
    document = make_document()
    real_chunk = uuid4()
    unit_of_work = MemoryUnitOfWork(document)
    runner = RunAnalysis(
        AnalysisDependencies(
            unit_of_work_factory=lambda: unit_of_work,
            retriever=StubRetriever(
                [Evidence(real_chunk, document.id, 8, "Sanção de multa de 10%.", 0.03)]
            ),
            llm_provider=SchemaProvider(
                extraction={
                    "findings": [
                        {
                            "category": "sanction",
                            "title": "Multa",
                            "value": "50%",
                            "citation_ids": [str(uuid4())],
                            "confidence": 0.99,
                        }
                    ]
                },
                critique={"decisions": [{"draft_index": 0, "supported": True, "confidence": 0.99}]},
            ),
            tool_registry=StubToolRegistry(
                ExternalValidation(status="unavailable", matches=None, source_url=None)
            ),
        )
    )

    await runner.execute("session-a", document.id)

    finding = unit_of_work.findings.items[0]
    assert finding.evidence_status == "unsupported"
    assert finding.citations == []
    assert finding.value == "50%"


@pytest.mark.asyncio
async def test_critic_marks_a_verified_external_conflict_explicitly() -> None:
    document = make_document()
    real_chunk = uuid4()
    unit_of_work = MemoryUnitOfWork(document)
    runner = RunAnalysis(
        AnalysisDependencies(
            unit_of_work_factory=lambda: unit_of_work,
            retriever=StubRetriever(
                [Evidence(real_chunk, document.id, 3, "CNPJ 12.345.678/0001-90.", 0.03)]
            ),
            llm_provider=SchemaProvider(
                extraction={
                    "findings": [
                        {
                            "category": "obligation",
                            "title": "Órgão contratante",
                            "value": "Entidade Alfa",
                            "citation_ids": [str(real_chunk)],
                            "confidence": 0.9,
                            "external_identifier": "12.345.678/0001-90",
                        }
                    ]
                },
                critique={"decisions": [{"draft_index": 0, "supported": True, "confidence": 0.9}]},
            ),
            tool_registry=StubToolRegistry(
                ExternalValidation(
                    status="verified",
                    matches=False,
                    source_url="https://dados.gov.br",
                )
            ),
        )
    )

    await runner.execute("session-a", document.id)

    assert unit_of_work.findings.items[0].evidence_status == "conflicting"
