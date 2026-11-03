from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PdfPolicy:
    max_bytes: int
    max_pages: int


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    number: int
    text: str


class IngestionError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
