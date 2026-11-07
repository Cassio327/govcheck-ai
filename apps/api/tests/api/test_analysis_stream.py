import json

import pytest

from tests.fixtures.pdf_factory import make_text_pdf

SESSION_HEADERS = {"X-Session-ID": "analysis-session"}


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n") if body.strip() else []:
        fields = {}
        for line in block.splitlines():
            key, value = line.split(": ", 1)
            fields[key] = value
        fields["id"] = int(fields["id"])
        fields["data"] = json.loads(fields["data"])
        events.append(fields)
    return events


@pytest.mark.asyncio
async def test_analysis_sse_replays_after_disconnect_without_duplicate_terminal(api_client) -> None:
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
    started = await api_client.post(
        f"/api/v1/documents/{document_id}/analysis", headers=SESSION_HEADERS
    )

    assert started.status_code == 202
    assert started.json()["status"] in {"running", "completed"}

    initial_stream = await api_client.get(
        f"/api/v1/documents/{document_id}/events", headers=SESSION_HEADERS
    )
    initial_events = parse_sse(initial_stream.text)
    assert len(initial_events) >= 5
    assert [event["id"] for event in initial_events] == list(range(1, len(initial_events) + 1))

    replay = await api_client.get(
        f"/api/v1/documents/{document_id}/events",
        headers={**SESSION_HEADERS, "Last-Event-ID": "2"},
    )
    replayed_events = parse_sse(replay.text)

    assert all(event["id"] > 2 for event in replayed_events)
    assert sum(event["event"] == "analysis.completed" for event in replayed_events) == 1
    findings = await api_client.get(
        f"/api/v1/documents/{document_id}/findings", headers=SESSION_HEADERS
    )
    assert findings.status_code == 200
    assert findings.json()[0]["evidence_status"] == "supported"
