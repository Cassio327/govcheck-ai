import type { ChangeEvent } from "react";

import { Icon } from "../../components/icon";
import type { DocumentRecord } from "../../lib/contracts";

interface Props {
  document: DocumentRecord | null;
  busy: boolean;
  onFile: (file: File) => void;
  onExample: () => void;
}

export function DocumentUpload({ document, busy, onFile, onExample }: Props) {
  function change(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onFile(file);
    event.currentTarget.value = "";
  }

  return (
    <section className="document-upload" id="documento" aria-label="Documento em análise">
      <div className="document-identity">
        <Icon name="file" />
        <div>
          <strong>{document?.filename ?? "Nenhum edital selecionado"}</strong>
          <span>{busy ? "Leitura e indexação em andamento" : document ? "PDF indexado e isolado nesta sessão" : "PDF com texto · até 5 MB e 50 páginas"}</span>
        </div>
      </div>
      <div className="upload-actions">
        <label className={`button primary ${busy ? "disabled" : ""}`}>
          <Icon name="upload" />
          <span>{busy ? "Processando PDF…" : "Selecionar PDF"}</span>
          <input aria-label="Selecionar PDF" type="file" accept="application/pdf,.pdf" disabled={busy} onChange={change} />
        </label>
        <button className="button secondary" type="button" disabled={busy} onClick={onExample}>
          <Icon name="file" /> Usar edital de exemplo
        </button>
      </div>
    </section>
  );
}
