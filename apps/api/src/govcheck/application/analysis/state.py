from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from govcheck.application.retrieve_evidence import Evidence, EvidenceRetriever
from govcheck.domain.analysis import ExternalValidation, FindingDraft, ToolRegistryPort
from govcheck.domain.findings import Finding
from govcheck.domain.llm import LLMProvider
from govcheck.domain.repositories import UnitOfWork


class AnalysisState(TypedDict):
    job_id: UUID
    document_id: UUID
    session_id: str
    evidence: list[Evidence]
    drafts: list[FindingDraft]
    validations: dict[int, ExternalValidation]
    findings: list[Finding]


@dataclass(frozen=True, slots=True)
class AnalysisDependencies:
    unit_of_work_factory: Callable[[], UnitOfWork]
    retriever: EvidenceRetriever
    llm_provider: LLMProvider
    tool_registry: ToolRegistryPort
