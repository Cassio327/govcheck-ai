# GovCheck AI — Product and Technical Design

## Intent

Build a portfolio-grade GovTech application before 13 November 2026 for Cássio Henrique's V-LAB AI specialist application. The product should demonstrate practical LLM use, prompt engineering, RAG, conversational interfaces, FastAPI, multi-agent orchestration, tool calling, cloud delivery, testing, and responsible AI practices in one coherent workflow.

The product is an evidence-grounded assistant for preliminary analysis of Brazilian public procurement notices. It helps a user understand a PDF, extract important obligations and deadlines, validate selected identifiers against public data sources, and generate an auditable report. It does not make final legal determinations.

## Goals

- Upload a text-based public procurement PDF and preserve page-level provenance.
- Ask questions in Portuguese and receive grounded answers with page and excerpt citations.
- Extract structured deadlines, qualification documents, monetary values, evaluation criteria, sanctions, and contractual obligations.
- Use a LangGraph workflow with genuinely distinct analysis, external-validation, evidence-critique, and synthesis responsibilities.
- Validate at least one extracted identifier through a real public API using constrained tool calling.
- Stream processing progress and answers through FastAPI Server-Sent Events.
- Export an evidence-backed report as Markdown and JSON.
- Run locally without paid services through Ollama and support a deployable Groq provider for the public demo.
- Include automated tests, a small evaluation suite, CI, Docker, cloud deployment, and recruiter-facing documentation.

## Non-goals for the deadline

- Final legal advice or a guarantee of compliance.
- Exhaustive validation against every Brazilian procurement law or government database.
- Fine-tuning a model in the main product path.
- OCR for scanned or handwritten documents.
- Production authentication, billing, organization workspaces, or long-term document retention.
- Support for arbitrary file formats beyond text-based PDF.
- A mobile application.

## Anti-goals

- A collection of disconnected framework demos described as “multi-agent.”
- Answers without page-level evidence when the claim comes from the uploaded document.
- Fabricated API results or a mock presented as a real external validation.
- A polished interface hiding an untested or non-reproducible backend.
- Excessive features that prevent a stable end-to-end demo by 12 November.

## Constraints

- Private repository during development, published only after the user approves the finished result.
- Delivery target: stable release by 10 November; 11–12 November reserved for QA, deployment, documentation, and contingency.
- The ChatGPT subscription is not a runtime API. Local execution will use Ollama; the hosted demo will use Groq after the user creates a free key and stores it as a secret.
- No secrets in source control, chat messages, screenshots, logs, fixtures, or reports.
- Development must remain explainable to the user for the technical interview.
- Repository code and technical documentation will use English. Product UI and sample questions will use Brazilian Portuguese. The README will provide an English overview and a concise Portuguese quick start.
- The user must connect a Railway account and create a Groq API key before the deployment milestone. Development and CI remain unblocked through deterministic fakes and optional Ollama.

## Approaches considered

### 1. Ollama-only local application

Lowest external dependency and no API key. It cannot provide a practical public cloud demo without costly model hosting, which weakens the portfolio submission.

### 2. Groq-only hosted application

Fastest path to a public demo, but local development and evaluation depend on a third-party key and service availability.

### 3. Provider-independent application: Ollama locally, Groq in deployment — selected

An `LLMProvider` boundary keeps prompts and structured outputs independent from transport. Ollama provides no-cost local use; Groq provides a responsive public demo. Tests use deterministic fakes, so CI never needs a secret. This is the selected approach because it is demonstrable, resilient, and itself shows sound AI application architecture.

## Product experience

The application has three primary screens:

1. **Workspace:** upload a PDF, see file validation, and follow ingestion progress.
2. **Analysis:** switch between a grounded chat and structured findings grouped by deadlines, documents, values, criteria, sanctions, and obligations. Every document-derived finding links to a page and excerpt.
3. **Report:** review external checks, warnings, confidence, missing evidence, and export the final Markdown or JSON report.

The UI must always distinguish:

- facts extracted from the PDF;
- values returned by an external source;
- model-generated interpretation;
- uncertain or unsupported claims;
- tool or provider failures.

## Architecture

The repository is a monorepo:

- `apps/api`: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, LangGraph.
- `apps/web`: Next.js, TypeScript, Tailwind CSS, accessible component primitives.
- `packages/evaluation`: versioned questions, expected evidence, and evaluation runner.
- `infra`: Docker Compose and deployment configuration.
- `docs`: architecture, threat model, evaluation results, and interview guide.

PostgreSQL stores document metadata, page-aware chunks, sessions, findings, citations, tool executions, and reports. `pgvector` stores multilingual embeddings produced locally with a small multilingual sentence-transformer. Retrieval combines vector similarity with lexical ranking and reciprocal-rank fusion. This avoids requiring a second paid embedding API.

### Processing flow

1. Validate size, MIME signature, extension, and page count.
2. Extract page-aware text with PyMuPDF; reject image-only PDFs with a clear OCR-not-supported message.
3. Normalize text, create overlapping chunks without losing page metadata, embed, and index.
4. Run structured extraction with schema validation and bounded retries.
5. Pass validated identifiers to allowlisted public-data tools.
6. Run an evidence critic that checks whether each claim has adequate supporting context and marks unsupported claims.
7. Produce a versioned report with citations, confidence labels, tool provenance, and a legal-use disclaimer.
8. Persist status transitions and stream progress to the web client over SSE.

### LangGraph responsibilities

- **Analysis node:** retrieves evidence and extracts typed findings.
- **External validation node:** invokes only registered tools with schema-validated arguments and records raw provenance.
- **Evidence critic node:** verifies citation support, conflicts, and missing context; it cannot silently invent replacement evidence.
- **Synthesis node:** formats approved findings into chat answers and reports.

Ingestion, persistence, FastAPI, and SSE are infrastructure, not agents.

### Conversational RAG

The chat rewrites follow-up questions only when required, retrieves hybrid evidence, and answers using the retrieved context. A document instruction is treated as untrusted data, not as a system instruction. When evidence is insufficient, the expected result is an explicit “not found in the document” response rather than a guessed answer.

### External tools

The MVP will implement one reliable real integration first, selected from official/public Brazilian company or procurement data sources after endpoint verification. A second integration is optional. Tools use strict schemas, domain allowlists, timeouts, retries, and visible failure states. Tests use recorded sanitized fixtures, never fabricated live-success claims.

## API surface

- `POST /api/v1/documents` — upload and begin ingestion.
- `GET /api/v1/documents/{id}` — document status and metadata.
- `GET /api/v1/documents/{id}/events` — SSE progress stream.
- `POST /api/v1/documents/{id}/analysis` — start structured analysis.
- `POST /api/v1/documents/{id}/chat` — grounded conversational query.
- `GET /api/v1/documents/{id}/findings` — typed findings and citations.
- `GET /api/v1/documents/{id}/report` — Markdown or JSON report.
- `GET /health` and `GET /ready` — operational probes.

OpenAPI is part of the portfolio deliverable. Error responses use a consistent typed envelope and never expose stack traces or secrets.

## Safety, privacy, and security

- Explicitly state that the tool supports preliminary analysis and is not legal advice.
- Enforce upload limits and parse only validated PDFs.
- Defend against prompt injection by separating instructions from document content, constraining tools, and checking evidence.
- Never execute document content or allow model-generated arbitrary URLs or code.
- Add basic rate limiting and timeouts for the public demo.
- Avoid collecting personal data; provide automatic demo-data cleanup where supported.
- Redact secrets and sensitive request headers from logs and traces.
- Document remaining risks in a compact threat model.
- The hosted demo will allow arbitrary text-based PDFs within strict limits (initial target: 5 MB and 50 pages), one active analysis per session, short-lived storage, and automatic deletion. It will also include a curated sample path so reviewers can test it instantly.

## Verification and evaluation

### Automated tests

- Unit tests for chunking, page provenance, schemas, ranking fusion, tool argument validation, provider adapters, and report rendering.
- Integration tests for upload-to-report flow with deterministic LLM and HTTP fakes.
- API contract tests for errors, streaming events, and report formats.
- Frontend component and critical-flow tests.
- CI runs linting, type checking, tests, migration checks, secret scanning, and builds without requiring an LLM key.

### AI evaluation

Use at least three public text-based notices and a versioned set of approximately 30 questions/findings. Report:

- citation recall;
- extraction precision/recall or field-level F1;
- unsupported-claim rate;
- answer correctness from a documented manual rubric;
- latency by pipeline stage.

Evaluation results must include limitations and failures, not only aggregate success numbers.

## Deployment and operations

- Local: Docker Compose for web, API, PostgreSQL/pgvector, and optional Ollama profile.
- Ollama is an optional local provider rather than a hard quick-start requirement. The initial target is a small model such as Llama 3.2 3B suitable for a typical 8 GB RAM development machine; provider configuration can be changed without code edits.
- Hosted: Railway is the preferred full-stack deployment target once connected; the exact service layout will be chosen from its current capabilities during implementation.
- Secrets are configured only in the deployment environment.
- Structured logs include request/session identifiers but not document contents by default.
- A seeded public sample and guided demo path make the application usable without finding a document first.

## Portfolio presentation

The public repository will include:

- a concise problem statement and responsible-use boundary;
- architecture diagram and design decisions;
- animated demonstration or short video;
- one-command local quick start;
- hosted demo and OpenAPI links;
- evaluation table with methodology;
- test and CI badges;
- roadmap that labels fine-tuning and OCR as future work;
- interview guide explaining RAG, LangGraph state, tool safety, provider abstraction, and measured limitations.

Commits will be small, meaningful, and ordered by actual implementation dependencies. History will communicate engineering progression without artificial commit inflation.

## Delivery sequence

1. Repository, design, issue milestones, monorepo scaffold, and CI.
2. Database, PDF ingestion, page provenance, chunking, and retrieval.
3. Provider adapters and cited conversational RAG.
4. Typed extraction and LangGraph analysis flow.
5. External tool integration and evidence critic.
6. Web workspace, chat, findings, report, and SSE experience.
7. End-to-end tests, AI evaluation, threat model, and hardening.
8. Cloud deployment, demo asset, README, interview guide, and final QA.

## Builder-owned calls

- Select the exact public API after checking current availability, terms, and response stability.
- Select the smallest suitable multilingual embedding model after a quick quality/memory comparison.
- Choose accessible UI primitives and exact visual styling.
- Adjust milestone boundaries when tests reveal a dependency, while preserving the MVP and deadline.
- Defer any optional second external integration, fine-tuning experiment, OCR, or advanced observability before compromising the core demo.
