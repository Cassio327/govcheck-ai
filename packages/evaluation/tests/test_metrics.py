from datetime import UTC, datetime

import pytest

from govcheck_eval.metrics import (
    citation_recall,
    evaluate,
    field_scores,
    rubric_score,
    summarize_stage_latency,
    unsupported_claim_rate,
)
from govcheck_eval.schemas import (
    EvaluationDataset,
    ExpectedFinding,
    ExpectedQuestion,
    FindingPrediction,
    PredictionBundle,
    QuestionPrediction,
    StageLatencySample,
)


def question(case_id: str, pages: set[int]) -> ExpectedQuestion:
    return ExpectedQuestion(
        id=case_id,
        document_id="doc-a",
        question="Pergunta de teste?",
        expected_answer="Resposta esperada.",
        expected_pages=pages,
        rubric=["identifica o fato", "não extrapola", "cita a fonte", "responde claramente"],
    )


def answer(
    case_id: str,
    pages: list[int],
    *,
    claims_total: int = 1,
    claims_unsupported: int = 0,
    score: int | None = 4,
) -> QuestionPrediction:
    return QuestionPrediction(
        question_id=case_id,
        answer="Resposta prevista.",
        cited_pages=pages,
        claims_total=claims_total,
        claims_unsupported=claims_unsupported,
        rubric_score=score,
    )


def finding(case_id: str, field: str, value: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=case_id,
        document_id="doc-a",
        category="value",
        field=field,
        value=value,
        expected_pages={1},
    )


def predicted_finding(field: str, value: str) -> FindingPrediction:
    return FindingPrediction(
        document_id="doc-a",
        category="value",
        field=field,
        value=value,
        cited_pages=[1],
    )


def test_zero_denominators_do_not_inflate_scores() -> None:
    assert citation_recall([], []) == 0
    assert unsupported_claim_rate([]) is None
    assert field_scores([], []).precision == 0
    assert field_scores([], []).recall == 0
    assert field_scores([], []).f1 == 0
    assert rubric_score([]).normalized_score is None


def test_duplicate_citations_do_not_inflate_recall() -> None:
    expected = [question("q1", {4, 5}), question("q2", {9})]
    predictions = [answer("q1", [4, 4, 4]), answer("q2", [9, 9])]

    assert citation_recall(expected, predictions) == pytest.approx(2 / 3)


def test_field_scores_count_partial_matches_and_wrong_values() -> None:
    expected = [finding("f1", "valor_total", "R$ 10,00"), finding("f2", "prazo", "20 dias")]
    predictions = [
        predicted_finding("valor_total", "R$ 10,00"),
        predicted_finding("prazo", "30 dias"),
        predicted_finding("campo_extra", "não esperado"),
    ]

    scores = field_scores(expected, predictions)

    assert scores.true_positives == 1
    assert scores.false_positives == 2
    assert scores.false_negatives == 1
    assert scores.precision == pytest.approx(1 / 3)
    assert scores.recall == pytest.approx(1 / 2)
    assert scores.f1 == pytest.approx(0.4)


def test_field_scores_reject_correct_value_under_the_wrong_semantic_field() -> None:
    expected = [finding("f1", "valor_total", "R$ 10,00")]
    predictions = [predicted_finding("prazo", "R$ 10,00")]

    scores = field_scores(expected, predictions)

    assert scores.true_positives == 0
    assert scores.false_positives == 1
    assert scores.false_negatives == 1


def test_field_scores_accept_a_versioned_semantic_field_alias() -> None:
    expected = [
        ExpectedFinding(
            id="f1",
            document_id="doc-a",
            category="value",
            field="valor_total",
            field_aliases={"Valor total da contratação"},
            value="R$ 10,00",
            expected_pages={1},
        )
    ]
    predictions = [predicted_finding("valor total da contratação", "R$ 10,00")]

    scores = field_scores(expected, predictions)

    assert scores.true_positives == 1
    assert scores.false_positives == 0
    assert scores.false_negatives == 0


def test_unsupported_claim_rate_and_manual_rubric_are_explicit() -> None:
    predictions = [
        answer("q1", [1], claims_total=2, claims_unsupported=1, score=4),
        answer("q2", [2], claims_total=3, claims_unsupported=1, score=2),
        answer("q3", [3], claims_total=0, claims_unsupported=0, score=None),
    ]

    assert unsupported_claim_rate(predictions) == pytest.approx(2 / 5)
    rubric = rubric_score(predictions)
    assert rubric.normalized_score == pytest.approx(0.75)
    assert rubric.scored_cases == 2
    assert rubric.pending_cases == 1


def test_missing_prediction_remains_pending_in_manual_rubric() -> None:
    rubric = rubric_score([answer("q1", [1], score=4)], expected_cases=2)

    assert rubric.normalized_score == 1
    assert rubric.scored_cases == 1
    assert rubric.pending_cases == 1


def test_latency_summary_keeps_missing_events_visible() -> None:
    samples = [
        StageLatencySample(document_id="doc-a", stage="extraction", milliseconds=100),
        StageLatencySample(document_id="doc-b", stage="extraction", milliseconds=300),
        StageLatencySample(document_id="doc-a", stage="synthesis", milliseconds=50),
    ]

    summary = summarize_stage_latency(
        samples,
        document_ids={"doc-a", "doc-b"},
        expected_stages=("extraction", "synthesis"),
    )

    assert summary.stages["extraction"].p50_ms == pytest.approx(200)
    assert summary.stages["extraction"].p95_ms == pytest.approx(290)
    assert summary.stages["synthesis"].p50_ms == 50
    assert summary.missing_events == 1


def test_evaluate_rejects_predictions_for_another_dataset_version() -> None:
    dataset = EvaluationDataset(version="2026.11", documents=[], questions=[], findings=[])
    predictions = PredictionBundle(
        dataset_version="other",
        run_id="test",
        provider="fake",
        created_at=datetime.now(UTC),
        questions=[],
        findings=[],
        latencies=[],
    )

    with pytest.raises(ValueError, match="dataset version"):
        evaluate(dataset, predictions)
