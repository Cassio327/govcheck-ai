import math
import re
from collections import Counter
from collections.abc import Callable, Sequence
from uuid import UUID

from govcheck.application.retrieve_evidence import Evidence
from govcheck.domain.documents import Chunk
from govcheck.domain.repositories import UnitOfWork
from govcheck.domain.retrieval import EmbeddingProvider

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class QueryEmbeddingError(RuntimeError):
    """Raised when an embedding provider violates the single-query contract."""


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _bm25_scores(chunks: Sequence[Chunk], query: str) -> dict[UUID, float]:
    query_terms = list(dict.fromkeys(_tokens(query)))
    documents = [_tokens(chunk.text) for chunk in chunks]
    if not query_terms or not documents:
        return {}

    average_length = sum(len(document) for document in documents) / len(documents) or 1.0
    document_frequencies = {
        term: sum(term in document for document in documents) for term in query_terms
    }
    scores: dict[UUID, float] = {}
    for chunk, document in zip(chunks, documents, strict=True):
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if frequency == 0:
                continue
            document_frequency = document_frequencies[term]
            inverse_frequency = math.log(
                1 + ((len(documents) - document_frequency + 0.5) / (document_frequency + 0.5))
            )
            denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * len(document) / average_length)
            score += inverse_frequency * (frequency * 2.5) / denominator
        if score > 0:
            scores[chunk.id] = score
    return scores


def _bounded_excerpt(text: str, query: str, maximum: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= maximum:
        return normalized

    first_match = min(
        (normalized.casefold().find(token) for token in _tokens(query)),
        key=lambda position: position if position >= 0 else len(normalized),
        default=0,
    )
    if first_match < 0:
        first_match = 0
    content_size = maximum - 1
    start = max(0, min(first_match - content_size // 3, len(normalized) - content_size))
    excerpt = normalized[start : start + content_size]
    if start > 0:
        excerpt = "…" + excerpt[1:]
    return excerpt[:-1] + "…"


class HybridRetriever:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        embedding_provider: EmbeddingProvider,
        rrf_k: int = 60,
        excerpt_chars: int = 320,
    ) -> None:
        if rrf_k <= 0:
            raise ValueError("rrf_k must be greater than zero")
        if excerpt_chars < 20:
            raise ValueError("excerpt_chars must be at least 20")
        self._unit_of_work_factory = unit_of_work_factory
        self._embedding_provider = embedding_provider
        self._rrf_k = rrf_k
        self._excerpt_chars = excerpt_chars

    async def search(
        self,
        document_id: UUID,
        query: str,
        limit: int = 8,
    ) -> list[Evidence]:
        if not query.strip() or limit <= 0:
            return []

        async with self._unit_of_work_factory() as unit_of_work:
            # The repository applies document_id in SQL before any candidate is ranked.
            chunks = await unit_of_work.documents.list_chunks(document_id)
        if not chunks:
            return []

        query_vectors = await self._embedding_provider.embed_documents([query])
        if len(query_vectors) != 1:
            raise QueryEmbeddingError(
                f"expected one query embedding, received {len(query_vectors)}"
            )
        query_vector = query_vectors[0]

        vector_ranking = sorted(
            chunks,
            key=lambda chunk: (
                -_cosine_similarity(chunk.embedding, query_vector),
                chunk.ordinal,
                str(chunk.id),
            ),
        )
        lexical_scores = _bm25_scores(chunks, query)
        lexical_ranking = sorted(
            (chunk for chunk in chunks if chunk.id in lexical_scores),
            key=lambda chunk: (-lexical_scores[chunk.id], chunk.ordinal, str(chunk.id)),
        )

        fused_scores: dict[UUID, float] = {}
        for ranking in (vector_ranking, lexical_ranking):
            for rank, chunk in enumerate(ranking, start=1):
                fused_scores[chunk.id] = fused_scores.get(chunk.id, 0.0) + 1.0 / (
                    self._rrf_k + rank
                )

        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        ranked_ids = sorted(
            fused_scores,
            key=lambda chunk_id: (
                -fused_scores[chunk_id],
                chunks_by_id[chunk_id].ordinal,
                str(chunk_id),
            ),
        )[:limit]
        return [
            Evidence(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                excerpt=_bounded_excerpt(chunk.text, query, self._excerpt_chars),
                score=fused_scores[chunk.id],
            )
            for chunk in (chunks_by_id[chunk_id] for chunk_id in ranked_ids)
        ]
