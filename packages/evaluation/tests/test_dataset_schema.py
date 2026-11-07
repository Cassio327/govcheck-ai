import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from govcheck_eval.schemas import EvaluationDataset, ExpectedQuestion, load_dataset

DATASET_ROOT = Path(__file__).parents[1] / "datasets"


def test_versioned_public_notice_dataset_is_complete_and_attributed() -> None:
    dataset = load_dataset(DATASET_ROOT)

    assert dataset.version == "2026.11.1"
    assert len(dataset.documents) == 3
    assert len(dataset.questions) == 15
    assert len(dataset.findings) == 15
    assert len({case.id for case in dataset.questions}) == len(dataset.questions)
    assert len({case.id for case in dataset.findings}) == len(dataset.findings)
    assert {case.document_id for case in dataset.questions} == {
        document.id for document in dataset.documents
    }
    assert all(document.attribution.source_url.startswith("https://") for document in dataset.documents)
    assert all(document.attribution.license_name for document in dataset.documents)
    assert all(document.sha256 and len(document.sha256) == 64 for document in dataset.documents)
    assert all(case.expected_pages for case in dataset.questions)
    assert all(case.expected_pages for case in dataset.findings)


def test_dataset_rejects_a_case_that_references_an_unknown_document() -> None:
    dataset = load_dataset(DATASET_ROOT)
    payload = dataset.model_dump(mode="json")
    payload["questions"][0]["document_id"] = "missing-document"

    with pytest.raises(ValidationError, match="unknown document"):
        EvaluationDataset.model_validate(payload)


def test_manifest_points_to_jsonl_and_source_attribution_files() -> None:
    manifest = json.loads((DATASET_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["questions_file"].endswith(".jsonl")
    assert manifest["findings_file"].endswith(".jsonl")
    for document in manifest["documents"]:
        assert (DATASET_ROOT / document["attribution_file"]).is_file()


def test_evidence_pages_are_strictly_one_based() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        ExpectedQuestion(
            id="invalid-page",
            document_id="doc-a",
            question="Pergunta?",
            expected_answer="Resposta.",
            expected_pages={0},
            rubric=["critério"],
        )
