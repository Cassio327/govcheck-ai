import pytest

from tests.fixtures.pdf_factory import make_text_pdf

SESSION_HEADERS = {"X-Session-ID": "chat-session"}


async def upload_document(api_client) -> str:
    response = await api_client.post(
        "/api/v1/documents",
        headers=SESSION_HEADERS,
        files={
            "file": (
                "edital.pdf",
                make_text_pdf(["As propostas serão recebidas até 13 de novembro."]),
                "application/pdf",
            )
        },
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_chat_returns_a_grounded_answer_and_rejects_other_sessions(api_client) -> None:
    document_id = await upload_document(api_client)

    response = await api_client.post(
        f"/api/v1/documents/{document_id}/chat",
        headers=SESSION_HEADERS,
        json={"question": "Qual é o prazo?"},
    )
    forbidden = await api_client.post(
        f"/api/v1/documents/{document_id}/chat",
        headers={"X-Session-ID": "other-session"},
        json={"question": "Qual é o prazo?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["citations"][0]["page_number"] == 1
    assert payload["citations"][0]["chunk_id"]
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "document_not_found"
