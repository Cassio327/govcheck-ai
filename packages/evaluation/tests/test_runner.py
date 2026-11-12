import json
from pathlib import Path

import pytest

from govcheck_eval.runner import (
    _canonical_field,
    _latencies_from_events,
    _parse_sse,
    _verify_document_bytes,
    build_parser,
    score_predictions,
)
from govcheck_eval.schemas import load_dataset

DATASET_ROOT = Path(__file__).parents[1] / "datasets"


def test_live_runner_maps_api_titles_to_versioned_semantic_fields() -> None:
    dataset = load_dataset(DATASET_ROOT)

    field = _canonical_field(
        dataset,
        document_id="ufpe-pe-90001-2024",
        category="value",
        title="Valor total da contratação",
    )

    assert field == "valor_total"


def test_stage_latency_uses_persisted_event_timestamps_not_poll_time() -> None:
    events = [
        {"id": 1, "event": "analysis.started", "data": {"recorded_at": "2026-11-07T10:00:00Z"}},
        {
            "id": 2,
            "event": "analysis.extraction.completed",
            "data": {"recorded_at": "2026-11-07T10:00:00.200000Z"},
        },
        {
            "id": 3,
            "event": "analysis.external_validation.skipped",
            "data": {"recorded_at": "2026-11-07T10:00:00.250000Z"},
        },
        {
            "id": 4,
            "event": "analysis.evidence_critic.completed",
            "data": {"recorded_at": "2026-11-07T10:00:00.400000Z"},
        },
        {
            "id": 5,
            "event": "analysis.synthesis.completed",
            "data": {"recorded_at": "2026-11-07T10:00:00.500000Z"},
        },
        {"id": 6, "event": "analysis.completed", "data": {"recorded_at": "2026-11-07T10:00:00.520000Z"}},
    ]

    samples = _latencies_from_events(events, "doc-a")
    by_stage = {sample.stage: sample.milliseconds for sample in samples}

    assert by_stage == pytest.approx(
        {
            "extraction": 200,
            "external_validation": 50,
            "evidence_critic": 150,
            "synthesis": 100,
            "total": 520,
        }
    )


def test_sse_parser_keeps_batched_replay_events() -> None:
    payload = (
        'id: 1\nevent: analysis.started\ndata: {"recorded_at":"2026-11-07T10:00:00Z"}'
        "\n\n"
        'id: 2\nevent: analysis.completed\ndata: {"recorded_at":"2026-11-07T10:00:01Z"}'
        "\n\n"
    )

    events = _parse_sse(payload)

    assert [event["id"] for event in events] == [1, 2]
    assert events[1]["data"]["recorded_at"] == "2026-11-07T10:00:01Z"


def test_live_runner_rejects_a_pdf_that_changed_since_labeling() -> None:
    document = load_dataset(DATASET_ROOT).documents[0]

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _verify_document_bytes(document, b"not the labeled PDF", Path("changed.pdf"))


def test_live_command_requires_an_explicit_provider_name() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "live",
                "--dataset-dir",
                "datasets",
                "--api-base-url",
                "http://localhost:8000",
                "--documents-dir",
                "pdfs",
                "--predictions-output",
                "predictions.json",
                "--output",
                "result.json",
            ]
        )


def test_score_runner_writes_reproducible_json_and_markdown(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    markdown = tmp_path / "evaluation.md"

    result = score_predictions(
        dataset_dir=DATASET_ROOT,
        predictions_path=DATASET_ROOT / "predictions" / "fake-baseline.json",
        output=output,
        markdown_output=markdown,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["run_id"] == result.run_id == "fake-baseline-2026-11-07"
    assert payload["citation_recall"] == pytest.approx(13 / 15)
    assert "não representa qualidade de um modelo real" in markdown.read_text(encoding="utf-8")
