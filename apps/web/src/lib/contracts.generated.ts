// Generated from FastAPI OpenAPI. Do not edit by hand.
// Run `make generate-contracts` after changing API schemas.

export interface DocumentResponse {
  id: string;
  filename: string;
  status: "uploaded" | "indexed" | "failed";
  created_at: string;
  expires_at: string;
}

export interface CitationResponse {
  page_number: number;
  excerpt: string;
  chunk_id: string;
}

export interface ChatAnswerResponse {
  text: string;
  citations: Array<CitationResponse>;
  confidence: number;
  grounded: boolean;
}

export interface AnalysisJobResponse {
  id: string;
  document_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
}

export interface FindingCitationResponse {
  chunk_id: string | null;
  page_number: number;
  excerpt: string;
}

export interface FindingResponse {
  id: string;
  category: "deadline" | "document" | "value" | "criterion" | "sanction" | "obligation";
  title: string;
  value: string;
  evidence_status: "supported" | "unsupported" | "conflicting";
  confidence: number;
  citations: Array<FindingCitationResponse>;
}
