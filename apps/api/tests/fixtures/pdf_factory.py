from collections.abc import Sequence

import pymupdf


def make_text_pdf(pages: Sequence[str], *, encrypted: bool = False) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    if encrypted:
        return document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password",
            user_pw="user-password",
        )
    return document.tobytes()
