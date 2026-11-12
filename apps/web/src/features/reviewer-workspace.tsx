"use client";

import { useState } from "react";

import { BrandMark } from "../components/brand-mark";
import { Icon } from "../components/icon";
import { ResponsibleUse } from "../components/responsible-use";
import { StatusTimeline } from "../components/status-timeline";
import { askDocument, downloadReport, getFindings, startAnalysis, uploadDocument, watchAnalysis } from "../lib/api";
import { createBrowserId } from "../lib/browser-id";
import type { DocumentRecord, Finding, StreamEvent } from "../lib/contracts";
import { downloadBlob } from "../lib/download";
import { ChatPanel, type ReviewerMessage } from "./chat/chat-panel";
import { FindingList } from "./findings/finding-list";
import { ValidationStatus } from "./findings/validation-status";
import { validationStateFromEvent, type ValidationState } from "./findings/validation-state";
import { ReportActions } from "./report/report-actions";
import { DocumentUpload } from "./upload/document-upload";

const EXAMPLE_DOCUMENT: DocumentRecord = {
  id: "example-edital",
  filename: "edital-exemplo-servicos-ti.pdf",
  status: "indexed",
  created_at: "2026-11-05T12:00:00Z",
  expires_at: "2026-11-06T12:00:00Z",
};

const EXAMPLE_FINDINGS: Finding[] = [
  {
    id: "example-deadline",
    category: "deadline",
    title: "Prazo para envio das propostas",
    value: "13 de novembro de 2026, às 18h",
    evidence_status: "supported",
    confidence: 0.94,
    citations: [{ chunk_id: "example-page-4", page_number: 4, excerpt: "As propostas serão recebidas até 13 de novembro de 2026, às 18h, exclusivamente por meio eletrônico." }],
  },
  {
    id: "example-qualification",
    category: "document",
    title: "Comprovação de capacidade técnica",
    value: "Atestado compatível com o objeto contratado",
    evidence_status: "supported",
    confidence: 0.88,
    citations: [{ chunk_id: "example-page-11", page_number: 11, excerpt: "A licitante deverá apresentar ao menos um atestado de capacidade técnica compatível com o objeto." }],
  },
  {
    id: "example-budget",
    category: "value",
    title: "Valor estimado da contratação",
    value: "R$ 480.000,00",
    evidence_status: "conflicting",
    confidence: 0.72,
    citations: [{ chunk_id: "example-page-7", page_number: 7, excerpt: "O valor estimado para a contratação é de R$ 480.000,00, conforme detalhamento do Anexo II." }],
  },
  {
    id: "example-obligation",
    category: "obligation",
    title: "Cadastro externo informado no edital",
    value: "Não foi possível confirmar na consulta pública",
    evidence_status: "unsupported",
    confidence: 0.31,
    citations: [],
  },
  {
    id: "example-sanction",
    category: "sanction",
    title: "Multa por atraso",
    value: "0,5% ao dia, limitada a 10%",
    evidence_status: "supported",
    confidence: 0.9,
    citations: [{ chunk_id: "example-page-19", page_number: 19, excerpt: "O atraso injustificado sujeitará a contratada à multa de 0,5% ao dia, limitada a 10% do valor da parcela." }],
  },
];

type Phase = "idle" | "uploading" | "analyzing" | "ready" | "error";

function exampleAnswer(question: string) {
  const normalized = question.toLocaleLowerCase("pt-BR");
  if (normalized.includes("document") || normalized.includes("atestado") || normalized.includes("capacidade")) {
    return {
      text: "O edital de demonstração exige ao menos um atestado de capacidade técnica compatível com o objeto contratado.",
      finding: EXAMPLE_FINDINGS[1],
    };
  }
  if (normalized.includes("sanção") || normalized.includes("sancao") || normalized.includes("multa")) {
    return {
      text: "O edital de demonstração prevê multa de 0,5% ao dia por atraso, limitada a 10% do valor da parcela.",
      finding: EXAMPLE_FINDINGS[4],
    };
  }
  if (normalized.includes("valor") || normalized.includes("orçamento") || normalized.includes("orcamento")) {
    return {
      text: "O PDF informa valor estimado de R$ 480.000,00, mas o achado está marcado como conflito e precisa de revisão humana.",
      finding: EXAMPLE_FINDINGS[2],
    };
  }
  if (normalized.includes("prazo") || normalized.includes("data") || normalized.includes("quando")) {
    return {
      text: "No edital de demonstração, o prazo para envio das propostas é 13 de novembro de 2026, às 18h.",
      finding: EXAMPLE_FINDINGS[0],
    };
  }
  return { text: "Não encontrei evidência suficiente no edital de demonstração para responder a essa pergunta.", finding: null };
}

function progressFor(event: StreamEvent): number {
  const progress: Record<string, number> = {
    "analysis.started": 2,
    "analysis.extraction.completed": 3,
    "analysis.external_validation.completed": 4,
    "analysis.external_validation.skipped": 4,
    "analysis.evidence_critic.completed": 5,
    "analysis.synthesis.completed": 5,
    "analysis.completed": 6,
  };
  return progress[event.event] ?? 2;
}

function triggerDownload(contents: string, type: string, filename: string) {
  downloadBlob(new Blob([contents], { type }), filename);
}

export function ReviewerWorkspace() {
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [messages, setMessages] = useState<ReviewerMessage[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [completed, setCompleted] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationState | null>(null);
  const [demo, setDemo] = useState(false);
  const [asking, setAsking] = useState(false);
  const [mobilePanel, setMobilePanel] = useState<"findings" | "chat">("findings");

  const busy = phase === "uploading" || phase === "analyzing";
  const ready = phase === "ready" && document !== null;

  function reset() {
    setFindings([]);
    setMessages([]);
    setCompleted(0);
    setError(null);
    setValidation(null);
    setDemo(false);
  }

  async function processFile(file: File) {
    reset();
    setDocument(null);
    setPhase("uploading");
    try {
      const uploaded = await uploadDocument(file);
      setDocument(uploaded);
      setCompleted(2);
      setPhase("analyzing");
      await startAnalysis(uploaded.id);
      for await (const event of watchAnalysis(uploaded.id)) {
        setCompleted(progressFor(event));
        if (event.event === "analysis.external_validation.skipped") setValidation("skipped");
        if (event.event === "analysis.external_validation.completed") {
          setValidation(validationStateFromEvent(event.data));
        }
        if (event.event === "analysis.failed") throw new Error("A análise não pôde ser concluída. Tente novamente.");
      }
      setFindings(await getFindings(uploaded.id));
      setCompleted(6);
      setPhase("ready");
    } catch (caught) {
      setPhase("error");
      setError(caught instanceof Error ? caught.message : "Não foi possível analisar este PDF.");
    }
  }

  function useExample() {
    reset();
    setDemo(true);
    setDocument(EXAMPLE_DOCUMENT);
    setFindings(EXAMPLE_FINDINGS);
    setCompleted(6);
    setValidation("unavailable");
    setPhase("ready");
  }

  async function ask(question: string) {
    if (!document) return;
    const userMessage: ReviewerMessage = { id: createBrowserId(), role: "user", text: question };
    setMessages((current) => [...current, userMessage]);
    setAsking(true);
    setError(null);
    try {
      const demonstration = exampleAnswer(question);
      const answer = demo
        ? {
            text: demonstration.text,
            citations: (demonstration.finding?.citations ?? []).map((citation) => ({ ...citation, chunk_id: citation.chunk_id ?? "example-source" })),
            confidence: demonstration.finding?.confidence ?? 0,
            grounded: Boolean(demonstration.finding?.citations.length),
          }
        : await askDocument(document.id, question);
      setMessages((current) => [...current, {
        id: createBrowserId(),
        role: "assistant",
        text: answer.text,
        citations: answer.citations,
        state: answer.grounded ? "answer" : "no_evidence",
      }]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Não foi possível responder agora.";
      setMessages((current) => [...current, { id: createBrowserId(), role: "assistant", text: message, state: "error" }]);
    } finally {
      setAsking(false);
    }
  }

  async function exportReport(format: "markdown" | "json") {
    if (!document) return;
    if (!demo) {
      await downloadReport(document.id, format);
      return;
    }
    const report = {
      notice: "Conteúdo demonstrativo. Análise preliminar; não substitui parecer jurídico.",
      document: document.filename,
      findings,
    };
    if (format === "json") {
      triggerDownload(JSON.stringify(report, null, 2), "application/json", "govcheck-demonstracao.json");
      return;
    }
    const rows = findings.map((item) => `## ${item.title}\n\n${item.value}\n\nEstado da evidência: ${item.evidence_status}`).join("\n\n");
    triggerDownload(`# Relatório GovCheck AI — demonstração\n\n> Análise preliminar; não substitui parecer jurídico.\n\n${rows}`, "text/markdown", "govcheck-demonstracao.md");
  }

  return (
    <div className="app-frame">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="GovCheck AI — início"><BrandMark /><span>GovCheck <b>AI</b></span></a>
        <nav aria-label="Navegação principal">
          <a href="#documento">Documento</a>
          <a href="#analise">Análise</a>
          <a href="#perguntas">Perguntas</a>
          <a href="#relatorio">Relatório</a>
        </nav>
        <span className="session-privacy"><Icon name="lock" /> Sessão isolada · armazenamento temporário</span>
        <a className="mobile-menu" href="#documento" aria-label="Ir para o documento"><Icon name="menu" /></a>
      </header>

      <ResponsibleUse />

      <main className="app-main" id="top">
        <div className="workspace-intro">
          <div>
            <span className="section-kicker">Revisão fundamentada</span>
            <h1>Analise o edital com a fonte ao lado.</h1>
          </div>
          <p>Extraia prazos, documentos, valores e obrigações. Cada conclusão precisa apontar para um trecho do PDF.</p>
        </div>

        {demo ? <div className="demo-notice" role="status"><strong>Modo demonstração</strong><span>Os dados abaixo são fictícios e servem apenas para explorar a interface.</span></div> : null}
        {error ? <div className="error-banner" role="alert"><strong>Não foi possível concluir.</strong><span>{error}</span></div> : null}

        <DocumentUpload document={document} busy={busy} onFile={processFile} onExample={useExample} />
        <StatusTimeline completed={completed} running={busy} />

        <div className="mobile-panel-switch" aria-label="Alternar painel">
          <button type="button" aria-pressed={mobilePanel === "findings"} className={mobilePanel === "findings" ? "active" : ""} onClick={() => setMobilePanel("findings")}>Achados</button>
          <button type="button" aria-pressed={mobilePanel === "chat"} className={mobilePanel === "chat" ? "active" : ""} onClick={() => setMobilePanel("chat")}>Perguntas</button>
        </div>

        <div className={`review-grid show-${mobilePanel}`} id="analise">
          <section className="review-panel findings-panel" aria-label="Revisão estruturada">
            <div className="panel-heading">
              <div>
                <span className="section-kicker">Achados estruturados</span>
                <h2>{ready ? `${findings.length} pontos para revisar` : "Aguardando análise"}</h2>
              </div>
              {ready ? <span className="review-state"><i /> Revisão humana necessária</span> : null}
            </div>
            {validation ? <ValidationStatus status={validation} /> : null}
            <FindingList findings={findings} defaultExpandedId={demo ? "example-deadline" : undefined} />
          </section>
          <div id="perguntas" className="chat-column">
            <ChatPanel enabled={ready} busy={asking} messages={messages} onAsk={ask} />
          </div>
        </div>

        <ReportActions enabled={ready} filename={document?.filename} onDownload={exportReport} />
      </main>

      <footer>
        <div><BrandMark /><strong>GovCheck AI</strong></div>
        <p>Projeto demonstrativo de IA aplicada a documentos públicos · evidência antes de conclusão.</p>
      </footer>
    </div>
  );
}
