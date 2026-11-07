import type {
  AnalysisJob,
  APIErrorEnvelope,
  ChatAnswer,
  DocumentRecord,
  Finding,
  StreamEvent,
} from "./contracts";
import { createBrowserId } from "./browser-id";
import { downloadBlob } from "./download";
import { SSEDecoder } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SESSION_STORAGE_KEY = "govcheck.session.v1";

function sessionId(): string {
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const created = createBrowserId();
  window.localStorage.setItem(SESSION_STORAGE_KEY, created);
  return created;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Session-ID", sessionId());
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = "Não foi possível concluir a solicitação.";
    try {
      const payload = (await response.json()) as APIErrorEnvelope;
      message = payload.error.message;
    } catch {
      // Keep the safe public fallback when an intermediary returns non-JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function uploadDocument(file: File): Promise<DocumentRecord> {
  const body = new FormData();
  body.append("file", file);
  return request<DocumentRecord>("/api/v1/documents", { method: "POST", body });
}

export async function startAnalysis(documentId: string): Promise<AnalysisJob> {
  return request<AnalysisJob>(`/api/v1/documents/${documentId}/analysis`, { method: "POST" });
}

export async function getFindings(documentId: string): Promise<Finding[]> {
  return request<Finding[]>(`/api/v1/documents/${documentId}/findings`);
}

export async function askDocument(documentId: string, question: string): Promise<ChatAnswer> {
  return request<ChatAnswer>(`/api/v1/documents/${documentId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export interface WatchAnalysisOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  pollIntervalMs?: number;
}

function abortError(): DOMException {
  return new DOMException("Acompanhamento cancelado.", "AbortError");
}

function wait(milliseconds: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(abortError());
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(abortError());
    };
    const timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function* streamEvents(response: Response): AsyncGenerator<StreamEvent> {
  if (!response.body) {
    const decoder = new SSEDecoder();
    yield* decoder.push(await response.text());
    yield* decoder.flush();
    return;
  }
  const reader = response.body.getReader();
  const text = new TextDecoder();
  const decoder = new SSEDecoder();
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      yield* decoder.push(text.decode(value, { stream: true }));
    }
    yield* decoder.push(text.decode());
    yield* decoder.flush();
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export async function* watchAnalysis(
  documentId: string,
  options: WatchAnalysisOptions = {},
): AsyncGenerator<StreamEvent> {
  let lastEventId = 0;
  const timeoutMs = options.timeoutMs ?? 300_000;
  const pollIntervalMs = options.pollIntervalMs ?? 500;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (options.signal?.aborted) throw abortError();
    const requestController = new AbortController();
    const forwardAbort = () => requestController.abort();
    options.signal?.addEventListener("abort", forwardAbort, { once: true });
    const requestTimer = window.setTimeout(
      () => requestController.abort(),
      Math.max(1, deadline - Date.now()),
    );
    try {
      const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/events`, {
        signal: requestController.signal,
        headers: {
          "X-Session-ID": sessionId(),
          ...(lastEventId ? { "Last-Event-ID": String(lastEventId) } : {}),
        },
      });
      if (!response.ok && response.status < 500) {
        throw new Error("Não foi possível acompanhar a análise.");
      }
      if (response.ok) {
        for await (const event of streamEvents(response)) {
          if (event.id <= lastEventId) continue;
          lastEventId = event.id;
          yield event;
          if (event.event === "analysis.completed" || event.event === "analysis.failed") return;
        }
      }
    } catch (caught) {
      if (options.signal?.aborted) throw abortError();
      if (Date.now() >= deadline) break;
      if (caught instanceof Error && caught.message === "Não foi possível acompanhar a análise.") {
        throw caught;
      }
      // Network and 5xx failures reconnect from the last persisted event.
    } finally {
      window.clearTimeout(requestTimer);
      options.signal?.removeEventListener("abort", forwardAbort);
    }
    await wait(pollIntervalMs, options.signal);
  }
  throw new Error("A análise excedeu o tempo de acompanhamento.");
}

export async function downloadReport(
  documentId: string,
  format: "markdown" | "json",
): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/report?format=${format}`, {
    headers: { "X-Session-ID": sessionId() },
  });
  if (!response.ok) throw new Error("Não foi possível gerar o relatório.");
  const blob = await response.blob();
  downloadBlob(blob, `govcheck-${documentId}.${format === "json" ? "json" : "md"}`);
}
