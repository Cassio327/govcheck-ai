from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from govcheck.application.chat_with_document import (
    DOCUMENT_NOT_FOUND_MESSAGE,
    ChatWithDocument,
    DocumentNotAccessible,
)
from govcheck.application.retrieve_evidence import Evidence
from govcheck.domain.documents import Document
from govcheck.infrastructure.llm.fake import FakeLLMProvider


class ChatDocumentRepository:
    def __init__(self, document: Document | None) -> None:
        self.document = document

    async def get_owned(self, document_id, session_id):
        if (
            self.document is not None
            and self.document.id == document_id
            and self.document.session_id == session_id
        ):
            return self.document
        return None


class ChatUnitOfWork:
    def __init__(self, repository: ChatDocumentRepository) -> None:
        self.documents = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class StubRetriever:
    def __init__(self, evidence: list[Evidence]) -> None:
        self.evidence = evidence
        self.calls = []

    async def search(self, document_id, query, limit=8):
        self.calls.append((document_id, query, limit))
        return self.evidence


def make_document() -> Document:
    return Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def make_service(document, retriever, provider, **kwargs) -> ChatWithDocument:
    repository = ChatDocumentRepository(document)
    return ChatWithDocument(
        unit_of_work_factory=lambda: ChatUnitOfWork(repository),
        retriever=retriever,
        llm_provider=provider,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_chat_returns_only_validated_citations() -> None:
    document = make_document()
    chunk_id = uuid4()
    evidence = Evidence(
        chunk_id=chunk_id,
        document_id=document.id,
        page_number=4,
        excerpt="As propostas serão recebidas até 13 de novembro.",
        score=0.03,
    )
    provider = FakeLLMProvider(
        structured_payload={
            "answer": "O prazo é 13 de novembro.",
            "citation_ids": [str(chunk_id)],
            "confidence": 0.92,
        }
    )
    service = make_service(document, StubRetriever([evidence]), provider)

    answer = await service.execute("session-a", document.id, "Qual é o prazo?")

    assert answer.text == "O prazo é 13 de novembro."
    assert answer.grounded is True
    assert answer.confidence == 0.92
    assert len(answer.citations) == 1
    assert answer.citations[0].chunk_id == chunk_id
    assert answer.citations[0].page_number == 4


@pytest.mark.asyncio
async def test_chat_refuses_when_retrieval_has_no_evidence() -> None:
    document = make_document()
    service = make_service(document, StubRetriever([]), FakeLLMProvider())

    answer = await service.execute("session-a", document.id, "Qual é o prazo?")

    assert answer.text == DOCUMENT_NOT_FOUND_MESSAGE
    assert answer.grounded is False
    assert answer.confidence == 0
    assert answer.citations == []


@pytest.mark.asyncio
async def test_chat_refuses_an_llm_citation_not_present_in_retrieval() -> None:
    document = make_document()
    evidence = Evidence(
        chunk_id=uuid4(),
        document_id=document.id,
        page_number=1,
        excerpt="Trecho do edital.",
        score=0.02,
    )
    provider = FakeLLMProvider(
        structured_payload={
            "answer": "Resposta inventada.",
            "citation_ids": [str(uuid4())],
            "confidence": 0.99,
        }
    )
    service = make_service(document, StubRetriever([evidence]), provider)

    answer = await service.execute("session-a", document.id, "Pergunta")

    assert answer.text == DOCUMENT_NOT_FOUND_MESSAGE
    assert answer.grounded is False
    assert answer.citations == []


@pytest.mark.asyncio
async def test_chat_enforces_document_ownership_before_retrieval() -> None:
    document = make_document()
    retriever = StubRetriever([])
    service = make_service(document, retriever, FakeLLMProvider())

    with pytest.raises(DocumentNotAccessible):
        await service.execute("other-session", document.id, "Qual é o prazo?")

    assert retriever.calls == []


@pytest.mark.asyncio
async def test_chat_includes_a_bounded_follow_up_history() -> None:
    document = make_document()
    chunk_id = uuid4()
    evidence = Evidence(
        chunk_id=chunk_id,
        document_id=document.id,
        page_number=2,
        excerpt="O prazo é sexta-feira.",
        score=0.03,
    )

    class RecordingProvider(FakeLLMProvider):
        def __init__(self):
            super().__init__(
                structured_payload={
                    "answer": "Sexta-feira.",
                    "citation_ids": [str(chunk_id)],
                    "confidence": 0.8,
                }
            )
            self.requests = []

        async def structured(self, messages, schema):
            self.requests.append(list(messages))
            return await super().structured(messages, schema)

    provider = RecordingProvider()
    service = make_service(
        document,
        StubRetriever([evidence]),
        provider,
        max_history_messages=2,
    )

    await service.execute("session-a", document.id, "Quando termina?")
    await service.execute("session-a", document.id, "E qual é o dia da semana?")

    second_prompt = provider.requests[1][-1].content
    assert "Quando termina?" in second_prompt
    assert "Sexta-feira." in second_prompt


@pytest.mark.asyncio
async def test_chat_stream_emits_text_then_a_validated_terminal_answer() -> None:
    document = make_document()
    chunk_id = uuid4()
    evidence = Evidence(
        chunk_id=chunk_id,
        document_id=document.id,
        page_number=3,
        excerpt="A sessão ocorrerá às 10h.",
        score=0.03,
    )
    service = make_service(
        document,
        StubRetriever([evidence]),
        FakeLLMProvider(
            structured_payload={
                "answer": "A sessão ocorrerá às 10h.",
                "citation_ids": [str(chunk_id)],
                "confidence": 0.9,
            }
        ),
    )

    deltas = [
        delta async for delta in service.stream("session-a", document.id, "Qual é o horário?")
    ]

    assert "".join(delta.text or "" for delta in deltas) == "A sessão ocorrerá às 10h."
    assert deltas[-1].type == "done"
    assert deltas[-1].answer is not None
    assert deltas[-1].answer.grounded is True


@pytest.mark.asyncio
async def test_chat_history_evicts_least_recent_session() -> None:
    document = make_document()
    service = make_service(
        document, StubRetriever([]), FakeLLMProvider(), max_history_sessions=1
    )

    await service.execute("session-a", document.id, "Primeira pergunta")
    assert ("session-a", document.id) in service._history

    another = document.model_copy(update={"session_id": "session-b"})
    service._unit_of_work_factory = lambda: ChatUnitOfWork(ChatDocumentRepository(another))
    await service.execute("session-b", document.id, "Outra pergunta")

    assert ("session-a", document.id) not in service._history
    assert ("session-b", document.id) in service._history


@pytest.mark.asyncio
async def test_chat_history_expires_idle_entries(monkeypatch) -> None:
    from govcheck.application import chat_with_document

    clock = [100.0]
    monkeypatch.setattr(chat_with_document, "monotonic", lambda: clock[0])
    document = make_document()
    service = make_service(
        document, StubRetriever([]), FakeLLMProvider(), history_ttl_seconds=30
    )

    await service.execute("session-a", document.id, "Pergunta antiga")
    assert len(service._history) == 1
    clock[0] += 31
    assert len(service._get_history("session-a", document.id)) == 0
    assert len(service._history) == 1
