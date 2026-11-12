from uuid import uuid4

import pytest
from pydantic import ValidationError

from govcheck.application.analysis.nodes import CriticDecisions, ExtractedFindings
from govcheck.application.chat_with_document import GroundedLLMAnswer
from govcheck.domain.analysis import FindingDraft


def _draft() -> dict[str, object]:
    return {
        "category": "deadline",
        "title": "Prazo de inscrição",
        "value": "Até 12 de novembro",
        "citation_ids": [str(uuid4())],
        "confidence": 0.9,
    }


@pytest.mark.parametrize(
    "oversized_field",
    [
        {"title": "X" * 256},
        {"value": "X" * 2_001},
        {"citation_ids": [str(uuid4()) for _ in range(7)]},
        {"external_identifier": "X" * 65},
    ],
)
def test_llm_draft_rejects_unbounded_strings_and_citations(oversized_field) -> None:
    with pytest.raises(ValidationError):
        FindingDraft.model_validate({**_draft(), **oversized_field})


def test_extraction_rejects_excessive_findings() -> None:
    with pytest.raises(ValidationError):
        ExtractedFindings.model_validate({"findings": [_draft() for _ in range(21)]})


def test_critic_rejects_excessive_decisions() -> None:
    with pytest.raises(ValidationError):
        CriticDecisions.model_validate(
            {
                "decisions": [
                    {"draft_index": index, "supported": True, "confidence": 0.9}
                    for index in range(21)
                ]
            }
        )


def test_chat_rejects_oversized_model_response() -> None:
    with pytest.raises(ValidationError):
        GroundedLLMAnswer.model_validate(
            {"answer": "X" * 4_001, "citation_ids": [str(uuid4())], "confidence": 0.9}
        )
