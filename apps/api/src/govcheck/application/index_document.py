from collections.abc import Callable
from uuid import UUID

from govcheck.domain.documents import Chunk
from govcheck.domain.ingestion import ExtractedPage
from govcheck.domain.repositories import UnitOfWork
from govcheck.domain.retrieval import EmbeddingProvider, chunk_pages


class EmbeddingCardinalityError(RuntimeError):
    """Raised before persistence when the provider drops or adds vectors."""


class IndexDocument:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        embedding_provider: EmbeddingProvider,
        target_chars: int = 1_200,
        overlap_chars: int = 180,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._embedding_provider = embedding_provider
        self._target_chars = target_chars
        self._overlap_chars = overlap_chars

    async def execute(self, document_id: UUID) -> int:
        async with self._unit_of_work_factory() as unit_of_work:
            pages = await unit_of_work.documents.list_pages(document_id)
            text_chunks = chunk_pages(
                [ExtractedPage(number=page.number, text=page.text) for page in pages],
                target_chars=self._target_chars,
                overlap_chars=self._overlap_chars,
            )
            vectors = await self._embedding_provider.embed_documents(
                [chunk.text for chunk in text_chunks]
            )
            if len(vectors) != len(text_chunks):
                raise EmbeddingCardinalityError(
                    f"{len(text_chunks)} chunks but {len(vectors)} embeddings"
                )

            chunks = [
                Chunk(
                    document_id=document_id,
                    page_number=text_chunk.page_number,
                    ordinal=text_chunk.ordinal,
                    text=text_chunk.text,
                    start_char=text_chunk.start_char,
                    end_char=text_chunk.end_char,
                    embedding=vector,
                )
                for text_chunk, vector in zip(text_chunks, vectors, strict=True)
            ]
            await unit_of_work.documents.add_chunks(chunks)
            await unit_of_work.commit()
            return len(chunks)
