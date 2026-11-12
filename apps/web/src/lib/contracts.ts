import type {
  AnalysisJobResponse,
  ChatAnswerResponse,
  DocumentResponse,
  FindingCitationResponse,
  FindingResponse,
} from "./contracts.generated";

export type DocumentRecord = DocumentResponse;
export type DocumentStatus = DocumentResponse["status"];
export type Citation = FindingCitationResponse;
export type Finding = FindingResponse;
export type EvidenceStatus = FindingResponse["evidence_status"];
export type ChatAnswer = ChatAnswerResponse;
export type AnalysisJob = AnalysisJobResponse;

export interface StreamEvent {
  id: number;
  event: string;
  data: Record<string, unknown>;
}

export interface APIErrorEnvelope {
  error: { code: string; message: string; request_id: string };
}
