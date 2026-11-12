"use client";

import { useEffect, useMemo, useState } from "react";

import { Icon } from "../../components/icon";
import { SourceCitation } from "../../components/source-citation";
import type { EvidenceStatus, Finding } from "../../lib/contracts";

const LABELS: Record<EvidenceStatus, string> = {
  supported: "Suportado",
  unsupported: "Sem evidência",
  conflicting: "Conflito",
};

const CATEGORIES: Array<{ key: Finding["category"]; label: string }> = [
  { key: "deadline", label: "Prazos" },
  { key: "document", label: "Documentos" },
  { key: "obligation", label: "Obrigações" },
  { key: "value", label: "Valores" },
  { key: "criterion", label: "Critérios" },
  { key: "sanction", label: "Sanções" },
];

export function FindingList({ findings, defaultExpandedId }: { findings: Finding[]; defaultExpandedId?: string }) {
  const populated = useMemo(() => CATEGORIES.filter(({ key }) => findings.some((item) => item.category === key)), [findings]);
  const [category, setCategory] = useState<Finding["category"]>(populated[0]?.key ?? "deadline");
  const [expanded, setExpanded] = useState<string | null>(defaultExpandedId ?? null);
  const visible = findings.filter((finding) => finding.category === category);

  useEffect(() => {
    if (populated.length && !populated.some((item) => item.key === category)) {
      setCategory(populated[0].key);
    }
  }, [category, populated]);

  useEffect(() => {
    if (defaultExpandedId && findings.some((item) => item.id === defaultExpandedId)) {
      setExpanded(defaultExpandedId);
    }
  }, [defaultExpandedId, findings]);

  if (!findings.length) {
    return <div className="empty-findings"><strong>Nenhum achado disponível.</strong><p>Envie um edital ou use o exemplo para iniciar a revisão.</p></div>;
  }

  return (
    <section className="findings" aria-label="Achados estruturados">
      <div className="category-tabs" aria-label="Filtrar categorias de achados">
        {populated.map(({ key, label }) => (
          <button key={key} type="button" aria-pressed={category === key} onClick={() => setCategory(key)}>
            {label} <span>{findings.filter((item) => item.category === key).length}</span>
          </button>
        ))}
      </div>
      <div className="finding-legend" aria-label="Legenda de evidências">
        {Object.entries(LABELS).map(([key, label]) => <span key={key} className={`status ${key}`}><i />{label}</span>)}
      </div>
      <ol className="finding-list">
        {visible.map((finding, index) => {
          const open = expanded === finding.id;
          return (
            <li key={finding.id} className={`finding-row ${finding.evidence_status} ${open ? "open" : ""}`}>
              <button type="button" aria-expanded={open} aria-controls={`finding-${finding.id}`} onClick={() => setExpanded(open ? null : finding.id)}>
                <span className="finding-number">{index + 1}</span>
                <span className="finding-copy"><strong>{finding.title}</strong><small>{finding.value}</small></span>
                <span className={`status ${finding.evidence_status}`}><i />{LABELS[finding.evidence_status]}</span>
                <span className="source-summary">{finding.citations[0] ? `Página ${finding.citations[0].page_number}` : "Sem fonte válida"}</span>
                <Icon name="chevron" className="chevron" />
              </button>
              {open ? <div className="finding-evidence" id={`finding-${finding.id}`}>
                <div className="evidence-heading"><strong>Evidência no edital</strong><span>Confiança {Math.round(finding.confidence * 100)}%</span></div>
                {finding.citations.length ? finding.citations.map((citation) => <SourceCitation key={`${citation.chunk_id}-${citation.page_number}`} citation={citation} />) : <p>O crítico de evidências não encontrou um trecho válido para sustentar esta interpretação.</p>}
              </div> : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
