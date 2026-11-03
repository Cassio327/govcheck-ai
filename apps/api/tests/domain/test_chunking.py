import pytest

from govcheck.domain.ingestion import ExtractedPage
from govcheck.domain.retrieval import chunk_pages


def test_chunk_pages_preserves_provenance_overlap_and_global_order() -> None:
    first_text = "alpha beta gamma delta epsilon zeta eta theta"
    pages = [
        ExtractedPage(number=1, text=first_text),
        ExtractedPage(number=2, text=""),
        ExtractedPage(number=3, text="prazo final amanhã"),
    ]

    chunks = chunk_pages(pages, target_chars=20, overlap_chars=5)

    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.page_number for chunk in chunks} == {1, 3}
    assert all(chunk.text for chunk in chunks)
    assert all(
        chunk.text
        == (first_text if chunk.page_number == 1 else pages[2].text)[
            chunk.start_char : chunk.end_char
        ].strip()
        for chunk in chunks
    )
    first_page_chunks = [chunk for chunk in chunks if chunk.page_number == 1]
    assert all(
        current.start_char < previous.end_char
        for previous, current in zip(first_page_chunks, first_page_chunks[1:], strict=False)
    )
    assert all(chunk.page_number == 1 for chunk in first_page_chunks)


def test_chunk_pages_keeps_a_short_page_in_one_chunk() -> None:
    chunks = chunk_pages(
        [ExtractedPage(number=7, text="documento obrigatório")],
        target_chars=1_200,
        overlap_chars=180,
    )

    assert len(chunks) == 1
    assert chunks[0].page_number == 7
    assert chunks[0].text == "documento obrigatório"
    assert (chunks[0].start_char, chunks[0].end_char) == (0, 21)


def test_chunk_pages_rejects_overlap_that_cannot_advance() -> None:
    with pytest.raises(ValueError, match="overlap_chars must be smaller"):
        chunk_pages([ExtractedPage(number=1, text="texto")], target_chars=10, overlap_chars=10)
