import pytest

from tests.fixtures.pdf_factory import make_text_pdf

SESSION_HEADERS = {"X-Session-ID": "reviewer-session"}


@pytest.mark.asyncio
async def test_upload_indexes_pdf_and_enforces_session_ownership(api_client) -> None:
    response = await api_client.post(
        "/api/v1/documents",
        headers=SESSION_HEADERS,
        files={
            "file": (
                "edital.pdf",
                make_text_pdf(["Prazo final: 13 de novembro. Documento obrigatório."]),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["filename"] == "edital.pdf"
    assert uploaded["status"] == "indexed"

    owned = await api_client.get(f"/api/v1/documents/{uploaded['id']}", headers=SESSION_HEADERS)
    forbidden = await api_client.get(
        f"/api/v1/documents/{uploaded['id']}", headers={"X-Session-ID": "other-session"}
    )

    assert owned.status_code == 200
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "document_not_found"
    assert forbidden.json()["error"]["request_id"]


@pytest.mark.asyncio
async def test_upload_returns_typed_errors_for_size_and_page_limits(api_client) -> None:
    oversized = await api_client.post(
        "/api/v1/documents",
        headers=SESSION_HEADERS,
        files={"file": ("large.pdf", b"%PDF-" + b"x" * 5_242_880, "application/pdf")},
    )
    too_many_pages = await api_client.post(
        "/api/v1/documents",
        headers=SESSION_HEADERS,
        files={
            "file": (
                "pages.pdf",
                make_text_pdf([f"Página {number}" for number in range(51)]),
                "application/pdf",
            )
        },
    )

    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "pdf_too_large"
    assert too_many_pages.status_code == 422
    assert too_many_pages.json()["error"]["code"] == "pdf_too_many_pages"
