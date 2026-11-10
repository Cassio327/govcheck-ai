import html
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from govcheck.domain.documents import utc_now
from govcheck.domain.repositories import UnitOfWork


def _markdown_text(value: str) -> str:
    """Escape document and model text before inserting it into Markdown."""
    normalized = " ".join(value.split())
    special = "\\`*_{}[]()#+-.!|>~"
    escaped = "".join(
        "\\" + character if character in special else character for character in normalized
    )
    return html.escape(escaped, quote=False)


RESPONSIBLE_USE = (
    "Esta análise é preliminar, pode conter limitações e não substitui parecer jurídico."
)


class DocumentNotAccessible(LookupError):
    """Raised without revealing that another session owns a document."""


@dataclass(frozen=True, slots=True)
class RenderedReport:
    markdown: str
    json_payload: dict[str, object]


class RenderReport:
    def __init__(self, *, unit_of_work_factory: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self, session_id: str, document_id: UUID) -> RenderedReport:
        async with self._unit_of_work_factory() as unit_of_work:
            document = await unit_of_work.documents.get_owned(document_id, session_id)
            if document is None:
                raise DocumentNotAccessible("document not found")
            findings = await unit_of_work.findings.list_for_document(document_id)
            tool_runs = await unit_of_work.tools.list_for_document(document_id)

        generated_at = utc_now()
        finding_payloads = [
            {
                "id": str(finding.id),
                "category": finding.category.value,
                "title": finding.title,
                "value": finding.value,
                "evidence_status": finding.evidence_status,
                "confidence": finding.confidence,
                "source_kind": "document_fact",
                "citations": [
                    {
                        "chunk_id": str(citation.chunk_id) if citation.chunk_id else None,
                        "page_number": citation.page_number,
                        "excerpt": citation.excerpt,
                    }
                    for citation in finding.citations
                ],
            }
            for finding in findings
        ]
        validation_payloads = [
            {
                "tool": run.name,
                "status": run.status,
                "request": run.request,
                "source_url": run.source_url,
                "checked_at": run.checked_at.isoformat(),
                "data": run.data,
                "error_code": run.error_code,
                "source_kind": "external_public_source",
            }
            for run in tool_runs
        ]
        json_payload: dict[str, object] = {
            "schema_version": "1.0",
            "generated_at": generated_at.isoformat(),
            "document": {
                "id": str(document.id),
                "filename": document.filename,
                "source_kind": "uploaded_pdf",
            },
            "findings": finding_payloads,
            "external_validations": validation_payloads,
            "responsible_use": {
                "notice": RESPONSIBLE_USE,
                "is_legal_advice": False,
            },
        }

        lines = [
            "# Relatório GovCheck AI",
            "",
            f"**Documento:** {_markdown_text(document.filename)}",
            f"**Gerado em:** {generated_at.isoformat()}",
            "",
            f"> {RESPONSIBLE_USE}",
            "",
            "## Achados do documento",
        ]
        if not findings:
            lines.extend(["", "Nenhum achado foi produzido."])
        for finding in findings:
            lines.extend(
                [
                    "",
                    f"### {_markdown_text(finding.title)}",
                    f"- Categoria: `{finding.category.value}`",
                    f"- Valor interpretado: {_markdown_text(finding.value)}",
                    f"- Evidência: `{finding.evidence_status}`",
                    f"- Confiança: {finding.confidence:.0%}",
                ]
            )
            for citation in finding.citations:
                lines.append(f"- Página {citation.page_number}: “{_markdown_text(citation.excerpt)}”")
        lines.extend(["", "## Verificações em fonte pública"])
        if not tool_runs:
            lines.extend(["", "Nenhuma verificação externa foi solicitada."])
        for run in tool_runs:
            lines.extend(
                [
                    "",
                    f"- `{run.name}` — `{run.status}`",
                    f"  - Fonte: {_markdown_text(run.source_url or 'indisponível')}",
                    f"  - Verificado em: {run.checked_at.isoformat()}",
                ]
            )
        return RenderedReport(markdown="\n".join(lines) + "\n", json_payload=json_payload)
