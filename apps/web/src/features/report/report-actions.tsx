"use client";

import { useState } from "react";

import { Icon } from "../../components/icon";

interface Props {
  enabled: boolean;
  filename?: string;
  onDownload: (format: "markdown" | "json") => Promise<void>;
}

export function ReportActions({ enabled, filename, onDownload }: Props) {
  const [busy, setBusy] = useState<"markdown" | "json" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(format: "markdown" | "json") {
    setBusy(format);
    setError(null);
    try {
      await onDownload(format);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível baixar o relatório.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="report-actions" id="relatorio" aria-label="Exportar relatório">
      <div>
        <span className="section-kicker">Relatório auditável</span>
        <h2>{filename ? `Revisão de ${filename}` : "Consolide a revisão"}</h2>
        <p>Fatos do PDF, interpretações do modelo e consultas externas permanecem separados.</p>
        {error ? <p className="inline-error" role="alert">{error}</p> : null}
      </div>
      <div className="report-buttons">
        <button className="button primary" type="button" disabled={!enabled || busy !== null} onClick={() => download("markdown")}>
          <Icon name="download" /> {busy === "markdown" ? "Preparando…" : "Baixar relatório Markdown"}
        </button>
        <button className="button secondary" type="button" disabled={!enabled || busy !== null} onClick={() => download("json")}>
          <Icon name="download" /> {busy === "json" ? "Preparando…" : "Exportar JSON"}
        </button>
      </div>
    </section>
  );
}
