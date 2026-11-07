import math
import re
import unicodedata
from collections import defaultdict
from datetime import UTC
from statistics import fmean

from govcheck_eval.schemas import (
    EvaluationDataset,
    EvaluationResult,
    ExpectedFinding,
    ExpectedQuestion,
    FieldScores,
    FindingPrediction,
    LatencyStats,
    PredictionBundle,
    QuestionPrediction,
    RubricSummary,
    StageLatencySample,
    StageLatencySummary,
)


def _divide(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def citation_recall(
    expected: list[ExpectedQuestion],
    predictions: list[QuestionPrediction],
) -> float:
    by_question = {prediction.question_id: set(prediction.cited_pages) for prediction in predictions}
    hits = 0
    total = 0
    for case in expected:
        expected_pages = set(case.expected_pages)
        total += len(expected_pages)
        hits += len(expected_pages & by_question.get(case.id, set()))
    return _divide(hits, total)


def field_scores(
    expected: list[ExpectedFinding],
    predictions: list[FindingPrediction],
) -> FieldScores:
    unmatched_predictions = set(range(len(predictions)))
    true_positives = 0
    for case in expected:
        for index in sorted(unmatched_predictions):
            prediction = predictions[index]
            if (
                prediction.document_id == case.document_id
                and prediction.category == case.category
                and normalize_label(prediction.field)
                in {
                    normalize_label(case.field),
                    *(normalize_label(alias) for alias in case.field_aliases),
                }
                and normalize_label(prediction.value) == normalize_label(case.value)
            ):
                true_positives += 1
                unmatched_predictions.remove(index)
                break
    false_positives = len(unmatched_predictions)
    false_negatives = len(expected) - true_positives
    precision = _divide(true_positives, true_positives + false_positives)
    recall = _divide(true_positives, true_positives + false_negatives)
    return FieldScores(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=_divide(2 * precision * recall, precision + recall),
    )

def unsupported_claim_rate(predictions: list[QuestionPrediction]) -> float | None:
    claims_total = sum(prediction.claims_total for prediction in predictions)
    if claims_total == 0:
        return None
    return _divide(
        sum(prediction.claims_unsupported for prediction in predictions),
        claims_total,
    )


def rubric_score(
    predictions: list[QuestionPrediction],
    *,
    max_score_per_case: int = 4,
    expected_cases: int | None = None,
) -> RubricSummary:
    scores = [
        prediction.rubric_score
        for prediction in predictions
        if prediction.rubric_score is not None
    ]
    total_cases = len(predictions) if expected_cases is None else expected_cases
    if total_cases < len(scores):
        raise ValueError("expected cases cannot be lower than scored cases")
    return RubricSummary(
        normalized_score=(
            _divide(sum(scores), len(scores) * max_score_per_case) if scores else None
        ),
        scored_cases=len(scores),
        pending_cases=total_cases - len(scores),
        max_score_per_case=max_score_per_case,
    )


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_stage_latency(
    samples: list[StageLatencySample],
    *,
    document_ids: set[str],
    expected_stages: tuple[str, ...],
) -> StageLatencySummary:
    values_by_stage: dict[str, list[float]] = defaultdict(list)
    observed: set[tuple[str, str]] = set()
    for sample in samples:
        if sample.document_id in document_ids and sample.stage in expected_stages:
            values_by_stage[sample.stage].append(sample.milliseconds)
            observed.add((sample.document_id, sample.stage))
    stages = {
        stage: LatencyStats(
            count=len(values),
            mean_ms=fmean(values),
            p50_ms=_percentile(values, 0.5),
            p95_ms=_percentile(values, 0.95),
        )
        for stage in expected_stages
        if (values := values_by_stage.get(stage, []))
    }
    expected_events = len(document_ids) * len(expected_stages)
    return StageLatencySummary(
        stages=stages,
        missing_events=max(0, expected_events - len(observed)),
        expected_events=expected_events,
    )


def evaluate(dataset: EvaluationDataset, predictions: PredictionBundle) -> EvaluationResult:
    if dataset.version != predictions.dataset_version:
        raise ValueError(
            f"dataset version mismatch: expected {dataset.version}, got {predictions.dataset_version}"
        )
    known_questions = {case.id for case in dataset.questions}
    unknown_questions = {
        prediction.question_id
        for prediction in predictions.questions
        if prediction.question_id not in known_questions
    }
    if unknown_questions:
        raise ValueError(f"unknown question prediction: {', '.join(sorted(unknown_questions))}")
    document_ids = {document.id for document in dataset.documents}
    unknown_documents = {
        prediction.document_id
        for prediction in predictions.findings
        if prediction.document_id not in document_ids
    }
    unknown_documents.update(
        sample.document_id for sample in predictions.latencies if sample.document_id not in document_ids
    )
    if unknown_documents:
        raise ValueError(f"unknown prediction document: {', '.join(sorted(unknown_documents))}")

    unknown_stages = {
        sample.stage for sample in predictions.latencies if sample.stage not in dataset.expected_stages
    }
    if unknown_stages:
        raise ValueError(f"unknown latency stage: {', '.join(sorted(unknown_stages))}")

    fields = field_scores(dataset.findings, predictions.findings)
    rubric = rubric_score(predictions.questions, expected_cases=len(dataset.questions))
    claims_total = sum(item.claims_total for item in predictions.questions)
    unsupported_claims = sum(item.claims_unsupported for item in predictions.questions)
    limitations = list(predictions.notes)
    if rubric.pending_cases:
        limitations.append(
            f"{rubric.pending_cases} resposta(s) aguardam avaliação manual da rubrica."
        )
    latency = summarize_stage_latency(
        predictions.latencies,
        document_ids=document_ids,
        expected_stages=dataset.expected_stages,
    )
    if latency.missing_events:
        wording = "evento está ausente" if latency.missing_events == 1 else "eventos estão ausentes"
        limitations.append(
            f"{latency.missing_events} de {latency.expected_events} {wording} na medição de latência."
        )
    return EvaluationResult(
        dataset_version=dataset.version,
        run_id=predictions.run_id,
        provider=predictions.provider,
        evaluated_at=predictions.created_at.astimezone(UTC),
        document_count=len(dataset.documents),
        question_count=len(dataset.questions),
        finding_count=len(dataset.findings),
        citation_recall=citation_recall(dataset.questions, predictions.questions),
        fields=fields,
        unsupported_claim_rate=unsupported_claim_rate(predictions.questions),
        claims_assessed=claims_total,
        unsupported_claims=unsupported_claims,
        rubric=rubric,
        latency=latency,
        limitations=limitations,
    )
