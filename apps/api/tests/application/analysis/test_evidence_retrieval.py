from types import SimpleNamespace
from uuid import uuid4

import pytest

from govcheck.application.analysis.nodes import (
    ANALYSIS_QUERIES,
    _collect_analysis_evidence,
)
from govcheck.application.retrieve_evidence import Evidence


class CategoryRetriever:
    def __init__(self, results):
        self.results = results
        self.queries = []

    async def search(self, document_id, query, limit=8):
        self.queries.append((document_id, query, limit))
        return self.results.get(query, [])


@pytest.mark.asyncio
async def test_analysis_retrieves_evidence_from_distinct_procurement_topics() -> None:
    document_id = uuid4()
    source_ids = [uuid4() for _ in ANALYSIS_QUERIES]
    results = {
        query: [
            Evidence(
                chunk_id=source_ids[index],
                document_id=document_id,
                page_number=index + 1,
                excerpt=f"Cláusula da categoria {index}",
                score=0.03,
            )
        ]
        for index, query in enumerate(ANALYSIS_QUERIES)
    }
    retriever = CategoryRetriever(results)

    evidence = await _collect_analysis_evidence(
        SimpleNamespace(retriever=retriever), document_id
    )

    assert [item.chunk_id for item in evidence] == source_ids
    assert [item.page_number for item in evidence] == list(range(1, 7))
    assert len(retriever.queries) == 6
    assert all(call[0] == document_id and call[2] == 4 for call in retriever.queries)


@pytest.mark.asyncio
async def test_analysis_deduplicates_chunks_and_ignores_other_documents() -> None:
    document_id = uuid4()
    shared = Evidence(uuid4(), document_id, 1, "Prazo das propostas", 0.03)
    unrelated = Evidence(uuid4(), uuid4(), 20, "Documento de outra sessão", 0.05)
    retriever = CategoryRetriever(
        {query: [shared, unrelated] for query in ANALYSIS_QUERIES}
    )

    evidence = await _collect_analysis_evidence(
        SimpleNamespace(retriever=retriever), document_id
    )

    assert evidence == [shared]


@pytest.mark.asyncio
async def test_analysis_keeps_a_bounded_round_robin_context() -> None:
    document_id = uuid4()
    results = {
        query: [
            Evidence(uuid4(), document_id, offset + 1, "Cláusula", 0.01)
            for offset in range(4)
        ]
        for query in ANALYSIS_QUERIES
    }
    retriever = CategoryRetriever(results)

    evidence = await _collect_analysis_evidence(
        SimpleNamespace(retriever=retriever), document_id
    )

    assert len(evidence) == 20
    assert len({item.chunk_id for item in evidence}) == 20
    assert [item.page_number for item in evidence[:6]] == [1] * 6
