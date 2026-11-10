import html
import re
from collections import deque
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable, Sequence
from importlib import resources
from time import monotonic
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from govcheck.application.retrieve_evidence import Evidence, EvidenceRetriever
from govcheck.domain.chat import ChatAnswer, ChatDelta, Citation
from govcheck.domain.llm import ChatMessage, LLMProvider
from govcheck.domain.repositories import UnitOfWork

DOCUMENT_NOT_FOUND_MESSAGE = (
    "Não encontrei evidências suficientes neste documento para responder com segurança."
)


class DocumentNotAccessible(LookupError):
    """Does not disclose whether a document exists for a different session."""


class GroundedLLMAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citation_ids: list[UUID]
    confidence: float = Field(ge=0, le=1)


def _prompt(name: str) -> str:
    return resources.files("govcheck.prompts").joinpath(name).read_text(encoding="utf-8")


class ChatWithDocument:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        retriever: EvidenceRetriever,
        llm_provider: LLMProvider,
        retrieval_limit: int = 8,
        max_history_messages: int = 6,
        max_history_sessions: int = 1_000,
        history_ttl_seconds: int = 3_600,
    ) -> None:
        if retrieval_limit <= 0:
            raise ValueError("retrieval_limit must be greater than zero")
        if max_history_messages < 0:
            raise ValueError("max_history_messages must not be negative")
        if max_history_sessions <= 0 or history_ttl_seconds <= 0:
            raise ValueError("history limits must be positive")
        self._unit_of_work_factory = unit_of_work_factory
        self._retriever = retriever
        self._llm_provider = llm_provider
        self._retrieval_limit = retrieval_limit
        self._history: OrderedDict[
            tuple[str, UUID], tuple[float, deque[tuple[str, str]]]
        ] = OrderedDict()
        self._max_history_messages = max_history_messages
        self._max_history_sessions = max_history_sessions
        self._history_ttl_seconds = history_ttl_seconds
        self._system_prompt = f"{_prompt('chat_system.md')}\n\n{_prompt('chat_answer.md')}"

    async def execute(
        self,
        session_id: str,
        document_id: UUID,
        question: str,
    ) -> ChatAnswer:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("question must not be empty")

        async with self._unit_of_work_factory() as unit_of_work:
            document = await unit_of_work.documents.get_owned(document_id, session_id)
        if document is None:
            raise DocumentNotAccessible("document not found")

        retrieved = await self._retriever.search(
            document_id,
            clean_question,
            self._retrieval_limit,
        )
        evidence = [item for item in retrieved if item.document_id == document_id]
        if not evidence:
            answer = self._not_found()
            self._remember(session_id, document_id, clean_question, answer.text)
            return answer

        messages = [
            ChatMessage(role="system", content=self._system_prompt),
            ChatMessage(
                role="user",
                content=self._user_prompt(
                    session_id,
                    document_id,
                    clean_question,
                    evidence,
                ),
            ),
        ]
        response = await self._llm_provider.structured(messages, GroundedLLMAnswer)
        evidence_by_id = {item.chunk_id: item for item in evidence}
        requested_ids = list(dict.fromkeys(response.citation_ids))
        if (
            not response.answer.strip()
            or not requested_ids
            or any(chunk_id not in evidence_by_id for chunk_id in requested_ids)
        ):
            answer = self._not_found()
        else:
            answer = ChatAnswer(
                text=response.answer.strip(),
                citations=[
                    Citation(
                        page_number=evidence_by_id[chunk_id].page_number,
                        excerpt=evidence_by_id[chunk_id].excerpt,
                        chunk_id=chunk_id,
                    )
                    for chunk_id in requested_ids
                ],
                confidence=response.confidence,
                grounded=True,
            )
        self._remember(session_id, document_id, clean_question, answer.text)
        return answer

    async def stream(
        self,
        session_id: str,
        document_id: UUID,
        question: str,
    ) -> AsyncIterator[ChatDelta]:
        answer = await self.execute(session_id, document_id, question)
        for part in re.findall(r"\S+\s*", answer.text):
            yield ChatDelta(type="text", text=part)
        yield ChatDelta(type="done", answer=answer)

    def _user_prompt(
        self,
        session_id: str,
        document_id: UUID,
        question: str,
        evidence: Sequence[Evidence],
    ) -> str:
        history = self._get_history(session_id, document_id)
        history_xml = "\n".join(
            f'<message role="{role}">{html.escape(content)}</message>' for role, content in history
        )
        evidence_xml = "\n".join(
            (
                f'<source id="{item.chunk_id}" page="{item.page_number}">'
                f"{html.escape(item.excerpt)}</source>"
            )
            for item in evidence
        )
        return (
            "<conversation_history>\n"
            f"{history_xml}\n"
            "</conversation_history>\n"
            f"<question>{html.escape(question)}</question>\n"
            '<document_evidence untrusted="true">\n'
            f"{evidence_xml}\n"
            "</document_evidence>"
        )

    def _remember(
        self,
        session_id: str,
        document_id: UUID,
        question: str,
        answer: str,
    ) -> None:
        history = self._get_history(session_id, document_id)
        history.append(("user", question))
        history.append(("assistant", answer))

    def _get_history(self, session_id: str, document_id: UUID) -> deque[tuple[str, str]]:
        """Bound conversation state by session count and idle lifetime."""
        now = monotonic()
        for key, (last_access, _) in list(self._history.items()):
            if now - last_access >= self._history_ttl_seconds:
                del self._history[key]
        key = (session_id, document_id)
        entry = self._history.pop(key, None)
        history = entry[1] if entry is not None else deque(maxlen=self._max_history_messages)
        self._history[key] = (now, history)
        while len(self._history) > self._max_history_sessions:
            self._history.popitem(last=False)
        return history

    @staticmethod
    def _not_found() -> ChatAnswer:
        return ChatAnswer(
            text=DOCUMENT_NOT_FOUND_MESSAGE,
            citations=[],
            confidence=0,
            grounded=False,
        )
