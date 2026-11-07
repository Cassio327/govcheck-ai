import html
from importlib import resources

from pydantic import BaseModel, ConfigDict, Field

from govcheck.application.analysis.state import AnalysisDependencies, AnalysisState
from govcheck.domain.analysis import ExternalValidation, FindingDraft
from govcheck.domain.findings import Citation, Finding
from govcheck.domain.llm import ChatMessage

ANALYSIS_QUERY = "prazos documentos valores critérios de julgamento sanções e obrigações do edital"


class ExtractedFindings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[FindingDraft] = Field(default_factory=list)


class CriticDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_index: int = Field(ge=0)
    supported: bool
    confidence: float = Field(ge=0, le=1)


class CriticDecisions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[CriticDecision] = Field(default_factory=list)


def _prompt(name: str) -> str:
    return resources.files("govcheck.prompts").joinpath(name).read_text(encoding="utf-8")


async def _record_event(
    dependencies: AnalysisDependencies,
    state: AnalysisState,
    event_type: str,
    payload: dict[str, object],
) -> None:
    async with dependencies.unit_of_work_factory() as unit_of_work:
        await unit_of_work.events.append(state["job_id"], event_type, payload)
        await unit_of_work.commit()


def build_nodes(dependencies: AnalysisDependencies):
    async def extract(state: AnalysisState) -> dict[str, object]:
        retrieved = await dependencies.retriever.search(
            state["document_id"],
            ANALYSIS_QUERY,
            20,
        )
        evidence = [item for item in retrieved if item.document_id == state["document_id"]]
        drafts: list[FindingDraft] = []
        if evidence:
            source_xml = "\n".join(
                (
                    f'<source id="{item.chunk_id}" page="{item.page_number}">'
                    f"{html.escape(item.excerpt)}</source>"
                )
                for item in evidence
            )
            result = await dependencies.llm_provider.structured(
                [
                    ChatMessage(role="system", content=_prompt("extract_findings.md")),
                    ChatMessage(
                        role="user",
                        content=(
                            '<document_evidence untrusted="true">\n'
                            f"{source_xml}\n"
                            "</document_evidence>"
                        ),
                    ),
                ],
                ExtractedFindings,
            )
            drafts = result.findings
        await _record_event(
            dependencies,
            state,
            "analysis.extraction.completed",
            {"finding_count": len(drafts), "evidence_count": len(evidence)},
        )
        return {"evidence": evidence, "drafts": drafts}

    async def external_validation(state: AnalysisState) -> dict[str, object]:
        validations: dict[int, ExternalValidation] = {}
        for index, draft in enumerate(state["drafts"]):
            if draft.external_identifier:
                validations[index] = await dependencies.tool_registry.validate_identifier(
                    draft.external_identifier,
                    document_id=state["document_id"],
                )
        status_counts = {
            status: sum(validation.status == status for validation in validations.values())
            for status in ("verified", "not_found", "unavailable", "invalid")
        }
        await _record_event(
            dependencies,
            state,
            "analysis.external_validation.completed",
            {
                "validation_count": len(validations),
                "validation_status_counts": status_counts,
            },
        )
        return {"validations": validations}

    async def validation_skipped(state: AnalysisState) -> dict[str, object]:
        await _record_event(
            dependencies,
            state,
            "analysis.external_validation.skipped",
            {"reason": "no_external_identifier"},
        )
        return {"validations": {}}

    async def evidence_critic(state: AnalysisState) -> dict[str, object]:
        decisions: list[CriticDecision] = []
        if state["drafts"]:
            evidence_by_id = {item.chunk_id: item for item in state["evidence"]}
            draft_xml = "\n".join(
                (
                    f'<claim index="{index}" '
                    f'citations="{",".join(str(item) for item in draft.citation_ids)}">'
                    f"{html.escape(draft.title)}: {html.escape(draft.value)}</claim>"
                )
                for index, draft in enumerate(state["drafts"])
            )
            evidence_xml = "\n".join(
                (
                    f'<source id="{item.chunk_id}" page="{item.page_number}">'
                    f"{html.escape(item.excerpt)}</source>"
                )
                for item in state["evidence"]
            )
            result = await dependencies.llm_provider.structured(
                [
                    ChatMessage(role="system", content=_prompt("critic.md")),
                    ChatMessage(
                        role="user",
                        content=f"<claims>\n{draft_xml}\n</claims>\n<sources>\n{evidence_xml}\n</sources>",
                    ),
                ],
                CriticDecisions,
            )
            decisions = result.decisions
        else:
            evidence_by_id = {}

        decisions_by_index = {item.draft_index: item for item in decisions}
        findings: list[Finding] = []
        for index, draft in enumerate(state["drafts"]):
            requested_ids = list(dict.fromkeys(draft.citation_ids))
            citations_are_valid = bool(requested_ids) and all(
                chunk_id in evidence_by_id for chunk_id in requested_ids
            )
            decision = decisions_by_index.get(index)
            is_supported = bool(decision and decision.supported and citations_are_valid)
            validation = state["validations"].get(index)
            if is_supported and validation is not None and validation.matches is False:
                evidence_status = "conflicting"
            elif is_supported:
                evidence_status = "supported"
            else:
                evidence_status = "unsupported"
            confidence = min(draft.confidence, decision.confidence) if decision else 0.0
            findings.append(
                Finding(
                    document_id=state["document_id"],
                    category=draft.category,
                    title=draft.title,
                    value=draft.value,
                    evidence_status=evidence_status,
                    confidence=confidence,
                    citations=(
                        [
                            Citation(
                                chunk_id=chunk_id,
                                page_number=evidence_by_id[chunk_id].page_number,
                                excerpt=evidence_by_id[chunk_id].excerpt,
                            )
                            for chunk_id in requested_ids
                        ]
                        if citations_are_valid
                        else []
                    ),
                )
            )

        await _record_event(
            dependencies,
            state,
            "analysis.evidence_critic.completed",
            {
                "supported_count": sum(
                    finding.evidence_status == "supported" for finding in findings
                ),
                "unsupported_count": sum(
                    finding.evidence_status == "unsupported" for finding in findings
                ),
                "conflicting_count": sum(
                    finding.evidence_status == "conflicting" for finding in findings
                ),
            },
        )
        return {"findings": findings}

    async def synthesize(state: AnalysisState) -> dict[str, object]:
        async with dependencies.unit_of_work_factory() as unit_of_work:
            await unit_of_work.findings.replace_for_document(
                state["document_id"], state["findings"]
            )
            await unit_of_work.events.append(
                state["job_id"],
                "analysis.synthesis.completed",
                {"finding_count": len(state["findings"])},
            )
            await unit_of_work.commit()
        return {}

    return extract, external_validation, validation_skipped, evidence_critic, synthesize


__all__ = ["ExternalValidation", "build_nodes"]
