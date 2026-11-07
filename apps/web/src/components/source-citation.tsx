import type { Citation } from "../lib/contracts";

export function SourceCitation({ citation }: { citation: Citation }) {
  return (
    <div className="citation">
      <blockquote>“{citation.excerpt}”</blockquote>
      <span className="citation-reference">Página {citation.page_number} · trecho exibido</span>
    </div>
  );
}
