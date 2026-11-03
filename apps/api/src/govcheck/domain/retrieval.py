from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from govcheck.domain.ingestion import ExtractedPage


@dataclass(frozen=True, slots=True)
class TextChunk:
    page_number: int
    ordinal: int
    text: str
    start_char: int
    end_char: int


class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...


def chunk_pages(
    pages: Sequence[ExtractedPage],
    *,
    target_chars: int = 1_200,
    overlap_chars: int = 180,
) -> list[TextChunk]:
    """Split page text without ever losing its source-page coordinates."""
    if target_chars <= 0:
        raise ValueError("target_chars must be greater than zero")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must not be negative")
    if overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be smaller than target_chars")

    chunks: list[TextChunk] = []
    ordinal = 0
    for page in pages:
        if not page.text.strip():
            continue

        start = 0
        while start < len(page.text):
            end = min(start + target_chars, len(page.text))
            raw_text = page.text[start:end]
            chunk_text = raw_text.strip()
            if chunk_text:
                chunks.append(
                    TextChunk(
                        page_number=page.number,
                        ordinal=ordinal,
                        text=chunk_text,
                        start_char=start,
                        end_char=end,
                    )
                )
                ordinal += 1

            if end == len(page.text):
                break
            start = max(start + 1, end - overlap_chars)

    return chunks
