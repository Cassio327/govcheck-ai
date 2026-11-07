from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from govcheck.application.analysis.graph import AnalysisDependencies, RunAnalysis
from govcheck.application.analysis.nodes import ExternalValidation
from govcheck.application.retrieve_evidence import Evidence
from govcheck.domain.documents import Document
from govcheck.domain.events import StreamEvent


class MemoryDocuments:
    def __init__(self, document):
        self.document = document

    async def get_owned(self, document_id, session_id):
        if document_id == self.document.id and session_id == self.document.session_id:
            return self.document
        return None


class MemoryFindings:
    def __init__(self):
        self.items = []

    async def replace_for_document(self, document_id, findings):
        self.items = [item for item in findings if item.document_id == document_id]


class MemoryEvents:
    def __init__(self):
        self.jobs = {}
        self.events = []

    async def add_job(self, job):
        self.jobs[job.id] = job

    async def update_job_status(self, job_id, status):
        self.jobs[job_id] = self.jobs[job_id].model_copy(update={"status": status})

    async def append(self, job_id, event_type, payload):
        event = StreamEvent(
            job_id=job_id,
            sequence=1 + sum(item.job_id == job_id for item in self.events),
            event_type=event_type,
            payload=payload,
        )
        self.events.append(event)
        return event


class MemoryUnitOfWork:
    def __init__(self, document):
        self.documents = MemoryDocuments(document)
        self.findings = MemoryFindings()
        self.events = MemoryEvents()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        return None


class StubRetriever:
    def __init__(self, evidence):
        self.evidence = evidence

    async def search(self, document_id, query, limit=8):
        return self.evidence


class SchemaProvider:
    def __init__(self, extraction, critique):
        self.extraction = extraction
        self.critique = critique

    async def structured(self, messages, schema):
        payload = self.extraction if schema.__name__ == "ExtractedFindings" else self.critique
        return schema.model_validate(payload)


class StubToolRegistry:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def validate_identifier(self, identifier):
        self.calls.append(identifier)
        return self.result


def make_document():
    return Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_graph_runs_distinct_nodes_and_replaces_findings_on_rerun() -> None:
    document = make_document()
    deadline_chunk = uuid4()
    registry = StubToolRegistry(
        ExternalValidation(status="verified", matches=True, source_url="https://dados.gov.br")
    )
    unit_of_work = MemoryUnitOfWork(document)
    dependencies = AnalysisDependencies(
        unit_of_work_factory=lambda: unit_of_work,
        retriever=StubRetriever(
            [
                Evidence(
                    chunk_id=deadline_chunk,
                    document_id=document.id,
                    page_number=4,
                    excerpt="Prazo final em 13 de novembro. CNPJ 12.345.678/0001-90.",
                    score=0.03,
                )
            ]
        ),
        llm_provider=SchemaProvider(
            extraction={
                "findings": [
                    {
                        "category": "deadline",
                        "title": "Prazo de propostas",
                        "value": "13 de novembro",
                        "citation_ids": [str(deadline_chunk)],
                        "confidence": 0.91,
                        "external_identifier": "12.345.678/0001-90",
                    }
                ]
            },
            critique={"decisions": [{"draft_index": 0, "supported": True, "confidence": 0.88}]},
        ),
        tool_registry=registry,
    )
    runner = RunAnalysis(dependencies)

    first_job = await runner.execute("session-a", document.id)
    second_job = await runner.execute("session-a", document.id)

    assert first_job.status == "completed"
    assert second_job.status == "completed"
    assert len(unit_of_work.findings.items) == 1
    assert unit_of_work.findings.items[0].evidence_status == "supported"
    assert unit_of_work.findings.items[0].citations[0].chunk_id == deadline_chunk
    assert registry.calls == ["12.345.678/0001-90", "12.345.678/0001-90"]
    first_event_types = [
        event.event_type for event in unit_of_work.events.events if event.job_id == first_job.id
    ]
    assert first_event_types == [
        "analysis.started",
        "analysis.extraction.completed",
        "analysis.external_validation.completed",
        "analysis.evidence_critic.completed",
        "analysis.synthesis.completed",
        "analysis.completed",
    ]


@pytest.mark.asyncio
async def test_graph_skips_external_validation_without_an_identifier() -> None:
    document = make_document()
    chunk_id = uuid4()
    registry = StubToolRegistry(
        ExternalValidation(status="verified", matches=True, source_url=None)
    )
    unit_of_work = MemoryUnitOfWork(document)
    runner = RunAnalysis(
        AnalysisDependencies(
            unit_of_work_factory=lambda: unit_of_work,
            retriever=StubRetriever(
                [Evidence(chunk_id, document.id, 1, "Documento obrigatório.", 0.03)]
            ),
            llm_provider=SchemaProvider(
                extraction={
                    "findings": [
                        {
                            "category": "document",
                            "title": "Certidão",
                            "value": "Certidão negativa",
                            "citation_ids": [str(chunk_id)],
                            "confidence": 0.8,
                        }
                    ]
                },
                critique={"decisions": [{"draft_index": 0, "supported": True, "confidence": 0.8}]},
            ),
            tool_registry=registry,
        )
    )

    job = await runner.execute("session-a", document.id)

    assert registry.calls == []
    event_types = [
        event.event_type for event in unit_of_work.events.events if event.job_id == job.id
    ]
    assert "analysis.external_validation.skipped" in event_types
