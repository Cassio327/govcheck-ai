import pytest

from tests.fixtures.pdf_factory import make_text_pdf

SESSION_HEADERS = {"X-Session-ID": "report-session"}


@pytest.mark.asyncio
async def test_report_exports_markdown_and_json_with_citations_and_disclaimer(api_client) -> None:
    upload = await api_client.post(
        "/api/v1/documents",
        headers=SESSION_HEADERS,
        files={
            "file": (
                "edital.pdf",
                make_text_pdf(["Prazo final para propostas: 13 de novembro."]),
                "application/pdf",
            )
        },
    )
    document_id = upload.json()["id"]
    await api_client.post(f"/api/v1/documents/{document_id}/analysis", headers=SESSION_HEADERS)

    markdown = await api_client.get(
        f"/api/v1/documents/{document_id}/report?format=markdown",
        headers=SESSION_HEADERS,
    )
    json_report = await api_client.get(
        f"/api/v1/documents/{document_id}/report?format=json",
        headers=SESSION_HEADERS,
    )

    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "não substitui parecer jurídico" in markdown.text
    assert "Página 1" in markdown.text
    assert json_report.status_code == 200
    payload = json_report.json()
    assert payload["schema_version"] == "1.0"
    assert payload["responsible_use"]["is_legal_advice"] is False
    assert payload["findings"][0]["citations"][0]["page_number"] == 1
