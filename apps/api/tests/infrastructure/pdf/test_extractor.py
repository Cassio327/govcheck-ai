import pytest

from govcheck.domain.ingestion import IngestionError, PdfPolicy
from govcheck.infrastructure.pdf.extractor import PdfExtractor
from tests.fixtures.pdf_factory import make_text_pdf


def test_extract_preserves_page_numbers_and_normalizes_whitespace() -> None:
    content = make_text_pdf(["Objeto: compra\nPrazo: 13 dias", "Documento    obrigatório"])

    pages = PdfExtractor().extract(content, PdfPolicy(max_bytes=1_000_000, max_pages=50))

    assert [(page.number, page.text) for page in pages] == [
        (1, "Objeto: compra Prazo: 13 dias"),
        (2, "Documento obrigatório"),
    ]


@pytest.mark.parametrize(
    ("content", "policy", "error_code"),
    [
        (b"not-a-pdf", PdfPolicy(max_bytes=1_000_000, max_pages=50), "invalid_pdf"),
        (b"%PDF-1.7\ncorrupt", PdfPolicy(max_bytes=1_000_000, max_pages=50), "invalid_pdf"),
        (make_text_pdf(["edital"], encrypted=True), PdfPolicy(1_000_000, 50), "encrypted_pdf"),
        (make_text_pdf([""]), PdfPolicy(1_000_000, 50), "ocr_required"),
        (make_text_pdf(["edital"]), PdfPolicy(max_bytes=10, max_pages=50), "file_too_large"),
        (
            make_text_pdf([f"Página {number}" for number in range(51)]),
            PdfPolicy(5_000_000, 50),
            "page_limit_exceeded",
        ),
    ],
    ids=[
        "invalid-signature",
        "corrupt-pdf",
        "encrypted-pdf",
        "image-only-pdf",
        "oversized-pdf",
        "too-many-pages",
    ],
)
def test_extract_rejects_unsafe_or_unsupported_pdf(
    content: bytes, policy: PdfPolicy, error_code: str
) -> None:
    with pytest.raises(IngestionError) as raised:
        PdfExtractor().extract(content, policy)

    assert raised.value.code == error_code
    assert raised.value.public_message
    assert "Traceback" not in raised.value.public_message
