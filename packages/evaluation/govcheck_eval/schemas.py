import json
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

FindingCategory = Literal[
    "deadline",
    "document",
    "value",
    "criterion",
    "sanction",
    "obligation",
]

DEFAULT_STAGES = (
    "indexing",
    "extraction",
    "external_validation",
    "evidence_critic",
    "synthesis",
    "total",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceAttribution(StrictModel):
    publisher: str = Field(min_length=1)
    source_url: str
    landing_page_url: str | None = None
    license_name: str = Field(min_length=1)
    license_url: str | None = None
    redistribution_status: Literal["reference_only", "redistributable"]
    accessed_on: date
    notes: str = Field(min_length=1)

    @field_validator("source_url", "landing_page_url", "license_url")
    @classmethod
    def validate_urls(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("source URLs must use HTTPS")
        return value


class DatasetDocument(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    title: str = Field(min_length=1)
    local_filename: str = Field(pattern=r"^[^/]+\.pdf$")
    text_based: bool
    artifact_status: Literal["download_required", "included"]
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    attribution: SourceAttribution


class ExpectedQuestion(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    document_id: str
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    expected_pages: set[PositiveInt] = Field(min_length=1)
    rubric: list[str] = Field(min_length=1)


class ExpectedFinding(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    document_id: str
    category: FindingCategory
    field: str = Field(min_length=1)
    field_aliases: set[str] = Field(default_factory=set)
    value: str = Field(min_length=1)
    expected_pages: set[PositiveInt] = Field(min_length=1)


class EvaluationDataset(StrictModel):
    version: str = Field(min_length=1)
    title: str = "GovCheck public-notice benchmark"
    description: str = ""
    expected_stages: tuple[str, ...] = DEFAULT_STAGES
    documents: list[DatasetDocument]
    questions: list[ExpectedQuestion]
    findings: list[ExpectedFinding]

    @model_validator(mode="after")
    def validate_references(self) -> "EvaluationDataset":
        document_ids = [document.id for document in self.documents]
        if len(set(document_ids)) != len(document_ids):
            raise ValueError("duplicate document id")
        known = set(document_ids)
        question_ids = [case.id for case in self.questions]
        finding_ids = [case.id for case in self.findings]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("duplicate question id")
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("duplicate finding id")
        unknown = {
            case.document_id
            for case in [*self.questions, *self.findings]
            if case.document_id not in known
        }
        if unknown:
            raise ValueError(f"case references unknown document: {', '.join(sorted(unknown))}")
        return self


class QuestionPrediction(StrictModel):
    question_id: str
    answer: str
    cited_pages: list[PositiveInt] = Field(default_factory=list)
    claims_total: int = Field(default=0, ge=0)
    claims_unsupported: int = Field(default=0, ge=0)
    rubric_score: int | None = Field(default=None, ge=0, le=4)
    latency_ms: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_claim_counts(self) -> "QuestionPrediction":
        if self.claims_unsupported > self.claims_total:
            raise ValueError("unsupported claims cannot exceed total claims")
        return self


class FindingPrediction(StrictModel):
    document_id: str
    category: FindingCategory
    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    cited_pages: list[PositiveInt] = Field(default_factory=list)


class StageLatencySample(StrictModel):
    document_id: str
    stage: str = Field(min_length=1)
    milliseconds: float = Field(ge=0)


class PredictionBundle(StrictModel):
    dataset_version: str
    run_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    created_at: datetime
    questions: list[QuestionPrediction]
    findings: list[FindingPrediction]
    latencies: list[StageLatencySample]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_measurements(self) -> "PredictionBundle":
        question_ids = [item.question_id for item in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("duplicate question prediction")
        latency_keys = [(item.document_id, item.stage) for item in self.latencies]
        if len(latency_keys) != len(set(latency_keys)):
            raise ValueError("duplicate stage latency sample")
        return self


class FieldScores(StrictModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


class RubricSummary(StrictModel):
    normalized_score: float | None
    scored_cases: int
    pending_cases: int
    max_score_per_case: int


class LatencyStats(StrictModel):
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float


class StageLatencySummary(StrictModel):
    stages: dict[str, LatencyStats]
    missing_events: int
    expected_events: int


class EvaluationResult(StrictModel):
    dataset_version: str
    run_id: str
    provider: str
    evaluated_at: datetime
    document_count: int
    question_count: int
    finding_count: int
    citation_recall: float
    fields: FieldScores
    unsupported_claim_rate: float | None
    claims_assessed: int
    unsupported_claims: int
    rubric: RubricSummary
    latency: StageLatencySummary
    limitations: list[str]


class ManifestDocument(StrictModel):
    id: str
    title: str
    local_filename: str
    text_based: bool
    artifact_status: Literal["download_required", "included"]
    sha256: str | None = None
    attribution_file: str


class DatasetManifest(StrictModel):
    version: str
    title: str
    description: str
    expected_stages: tuple[str, ...] = DEFAULT_STAGES
    questions_file: str
    findings_file: str
    documents: list[ManifestDocument]


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from error
        if not isinstance(payload, dict):
            raise TypeError(f"JSONL row must be an object at {path}:{line_number}")
        rows.append(payload)
    return rows


def load_dataset(root: Path) -> EvaluationDataset:
    root = root.resolve()
    manifest = DatasetManifest.model_validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    documents: list[DatasetDocument] = []
    for item in manifest.documents:
        attribution = SourceAttribution.model_validate_json(
            (root / item.attribution_file).read_text(encoding="utf-8")
        )
        documents.append(
            DatasetDocument(
                id=item.id,
                title=item.title,
                local_filename=item.local_filename,
                text_based=item.text_based,
                artifact_status=item.artifact_status,
                sha256=item.sha256,
                attribution=attribution,
            )
        )
    return EvaluationDataset(
        version=manifest.version,
        title=manifest.title,
        description=manifest.description,
        expected_stages=manifest.expected_stages,
        documents=documents,
        questions=[
            ExpectedQuestion.model_validate(item)
            for item in _load_jsonl(root / manifest.questions_file)
        ],
        findings=[
            ExpectedFinding.model_validate(item)
            for item in _load_jsonl(root / manifest.findings_file)
        ],
    )
