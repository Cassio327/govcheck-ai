import re

import pymupdf

from govcheck.domain.ingestion import ExtractedPage, IngestionError, PdfPolicy

WHITESPACE = re.compile(r"\s+")


class PdfExtractor:
    def extract(self, content: bytes, policy: PdfPolicy) -> list[ExtractedPage]:
        if len(content) > policy.max_bytes:
            raise IngestionError(
                "file_too_large",
                "O PDF excede o limite de tamanho permitido.",
            )
        if not content.startswith(b"%PDF-"):
            raise IngestionError("invalid_pdf", "Não foi possível ler o PDF enviado.")

        try:
            document = pymupdf.open(stream=content, filetype="pdf")
        except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
            raise IngestionError("invalid_pdf", "Não foi possível ler o PDF enviado.") from error

        try:
            if document.needs_pass:
                raise IngestionError(
                    "encrypted_pdf",
                    "O PDF está protegido por senha. Envie uma cópia desbloqueada.",
                )
            if document.page_count > policy.max_pages:
                raise IngestionError(
                    "page_limit_exceeded",
                    f"O PDF excede o limite de {policy.max_pages} páginas.",
                )

            pages = [
                ExtractedPage(
                    number=index + 1,
                    text=WHITESPACE.sub(" ", document[index].get_text("text")).strip(),
                )
                for index in range(document.page_count)
            ]
        except IngestionError:
            raise
        except (RuntimeError, ValueError) as error:
            raise IngestionError("invalid_pdf", "Não foi possível ler o PDF enviado.") from error
        finally:
            document.close()

        if not any(page.text for page in pages):
            raise IngestionError(
                "ocr_required",
                "O PDF não contém texto pesquisável. Envie um arquivo com OCR.",
            )
        return pages
