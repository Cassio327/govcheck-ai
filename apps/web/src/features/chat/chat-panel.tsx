"use client";

import { FormEvent, useState } from "react";

import { Icon } from "../../components/icon";
import { SourceCitation } from "../../components/source-citation";
import type { Citation } from "../../lib/contracts";

export interface ReviewerMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  state?: "answer" | "no_evidence" | "error";
}

const SUGGESTIONS = ["Qual é o prazo?", "Quais documentos são exigidos?", "Há sanções previstas?"];

interface Props {
  enabled: boolean;
  busy: boolean;
  messages: ReviewerMessage[];
  onAsk: (question: string) => Promise<void>;
}

export function ChatPanel({ enabled, busy, messages, onAsk }: Props) {
  const [question, setQuestion] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clean = question.trim();
    if (!clean || !enabled || busy) return;
    setQuestion("");
    await onAsk(clean);
  }

  return (
    <section className="chat-panel" aria-label="Perguntas sobre o edital">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Perguntas</span>
          <h2>Converse com o documento</h2>
        </div>
        <span className="grounding-label"><i /> Respostas com fontes</span>
      </div>

      <div className="chat-transcript" aria-live="polite">
        {!messages.length ? (
          <div className="chat-empty">
            <span className="chat-monogram">G</span>
            <strong>{enabled ? "O edital está pronto para perguntas." : "Selecione um edital para começar."}</strong>
            <p>As respostas são limitadas ao conteúdo recuperado do PDF e mostram a página usada.</p>
          </div>
        ) : null}
        {messages.map((message) => (
          <article key={message.id} className={`message ${message.role} ${message.state ?? ""}`} role={message.state === "error" ? "alert" : undefined}>
            <span className="message-author">{message.role === "user" ? "Você" : "GovCheck"}</span>
            <p>{message.text}</p>
            {message.role === "assistant" && message.state === "no_evidence" ? (
              <span className="ungrounded-warning">Não há evidência suficiente no PDF para responder.</span>
            ) : null}
            {message.citations?.map((citation) => (
              <SourceCitation key={`${message.id}-${citation.chunk_id}-${citation.page_number}`} citation={citation} />
            ))}
          </article>
        ))}
        {busy ? <div className="thinking" role="status"><i /><i /><i /><span>Buscando evidências no PDF</span></div> : null}
      </div>

      <div className="question-suggestions" aria-label="Perguntas sugeridas">
        {SUGGESTIONS.map((suggestion) => (
          <button key={suggestion} type="button" disabled={!enabled || busy} onClick={() => setQuestion(suggestion)}>{suggestion}</button>
        ))}
      </div>
      <form className="question-form" onSubmit={submit}>
        <label htmlFor="document-question" className="sr-only">Pergunta sobre o edital</label>
        <textarea
          id="document-question"
          aria-label="Pergunta sobre o edital"
          value={question}
          disabled={!enabled || busy}
          rows={2}
          maxLength={2000}
          placeholder={enabled ? "Pergunte algo que possa ser localizado no edital…" : "Carregue um PDF para habilitar perguntas"}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button className="send-button" type="submit" aria-label="Enviar pergunta" disabled={!enabled || busy || !question.trim()}>
          <Icon name="send" />
        </button>
      </form>
      <p className="chat-footnote"><Icon name="info" /> Verifique sempre os trechos citados antes de tomar uma decisão.</p>
    </section>
  );
}
