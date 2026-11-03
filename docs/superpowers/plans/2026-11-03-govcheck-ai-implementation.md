# GovCheck AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a stable, deployed GovTech portfolio application that analyzes Brazilian public-procurement PDFs with evidence-grounded RAG, a real LangGraph workflow, constrained public-data tools, streaming FastAPI endpoints, and a polished Portuguese web interface.

**Architecture:** A monorepo contains a FastAPI service, a Next.js client, a PostgreSQL/pgvector database, and a versioned evaluation package. The API separates domain contracts from infrastructure, provides interchangeable fake/Ollama/Groq LLM adapters, and persists page-aware evidence. LangGraph coordinates analysis, external validation, evidence criticism, and synthesis; deterministic fakes keep tests and CI independent from external credentials.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, LangGraph, PyMuPDF, sentence-transformers, pgvector, rank-bm25, httpx, pytest; Next.js, TypeScript, Tailwind CSS, Vitest, Playwright; PostgreSQL 16 + pgvector, Docker Compose, GitHub Actions, Railway.

**Spec:** `docs/superpowers/specs/2026-11-02-govcheck-ai-design.md`

## Global Constraints

- Private `Cassio327/govcheck-ai` repository until Cássio approves publication.
- Stable release by 10 November 2026; 11–12 November are QA, deployment, documentation, and contingency days.
- Repository code and technical documentation in English; UI and sample questions in Brazilian Portuguese; README English-first with a Portuguese quick start.
- No Groq key or other secret in source, fixtures, tests, logs, screenshots, reports, or CI.
- CI must pass without network access to an LLM and without an LLM secret.
- The product must say it supports preliminary analysis and is not legal advice.
- Hosted upload policy starts at 5 MiB, 50 pages, one active analysis per session, short-lived storage, and automatic deletion.
- PDF-derived claims require a page and excerpt; insufficient evidence produces an explicit “not found in the document” result.
- Document text is untrusted data and can never supply system instructions or arbitrary tool targets.
- Optional features—OCR, a second external integration, fine-tuning, accounts, billing, and advanced observability—must not delay the MVP.

## File Structure

```text
.
├── .github/workflows/ci.yml
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── compose.yaml
├── apps
│   ├── api
│   │   ├── Dockerfile
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── pyproject.toml
│   │   ├── src/govcheck
│   │   │   ├── api/                 # HTTP routes, dependencies, SSE envelopes
│   │   │   ├── application/         # Use cases and orchestration services
│   │   │   ├── domain/              # Typed entities, ports, policies
│   │   │   ├── infrastructure/      # Database, PDF, LLM, embedding, HTTP tools
│   │   │   ├── prompts/             # Versioned system/user prompt templates
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   └── tests/
│   └── web
│       ├── Dockerfile
│       ├── package.json
│       ├── src/app/
│       ├── src/components/
│       ├── src/features/
│       ├── src/lib/
│       └── tests/
├── packages/evaluation
│   ├── datasets/
│   ├── govcheck_eval/
│   ├── pyproject.toml
│   └── tests/
├── docs
│   ├── architecture.md
│   ├── evaluation.md
│   ├── interview-guide.md
│   ├── threat-model.md
│   └── superpowers/
└── infra/railway/
```

## Review Focus

- Corrupt, encrypted, image-only, oversized, or over-page-limit PDFs must fail with a typed Portuguese error; pinned in Task 4 ingestion tests.
- Evidence from one document must never appear in another document’s answer; pinned in Task 6 retrieval isolation tests.
- Prompt-injection text inside a notice must be quoted as data and must not alter tools or system behavior; pinned in Task 7 chat safety tests.
- Public-data APIs may time out, rate-limit, or return malformed data; the report must show an unavailable check rather than a fabricated result; pinned in Task 9 tool tests.
- SSE clients may disconnect and reconnect; replay from the last event ID must not duplicate terminal events; pinned in Task 10 API streaming tests.

---

### Task 1: Reproducible monorepo foundation and health path

**Files:**
- Create: `.editorconfig`, `.gitignore`, `.env.example`, `Makefile`, `compose.yaml`
- Create: `apps/api/pyproject.toml`, `apps/api/src/govcheck/__init__.py`, `apps/api/src/govcheck/config.py`, `apps/api/src/govcheck/main.py`
- Create: `apps/api/src/govcheck/api/routes/health.py`, `apps/api/tests/api/test_health.py`
- Create: `apps/web/package.json`, `apps/web/tsconfig.json`, `apps/web/next.config.ts`, `apps/web/src/app/page.tsx`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `Settings` loaded through `get_settings() -> Settings`; FastAPI `app`; `GET /health -> {"status": "ok"}`; `GET /ready -> {"status": "ready" | "not_ready"}`.

- [ ] **Step 1: Write failing health and configuration tests**

Create `test_health_returns_ok`, `test_ready_reports_missing_database`, and `test_settings_reject_production_without_database_url`; assert exact status codes and JSON envelopes.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/api/test_health.py -v`

Expected: FAIL because `govcheck.main` and `Settings` do not exist.

- [ ] **Step 3: Add the smallest API, typed settings, package configuration, web shell, Docker services, and CI needed by the tests**

`Settings` must expose `environment`, `database_url`, `llm_provider`, `groq_api_key`, `ollama_base_url`, `max_upload_bytes=5_242_880`, `max_pdf_pages=50`, and `retention_minutes=60`. Secret fields use Pydantic secret types and never appear in `repr`.

- [ ] **Step 4: Run backend tests and build the web shell**

Run: `make test-api && make build-web`

Expected: health tests PASS and Next.js production build exits 0.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: establish reproducible monorepo foundation"
```

### Task 2: Domain contracts and deterministic LLM boundary

**Files:**
- Create: `apps/api/src/govcheck/domain/llm.py`
- Create: `apps/api/src/govcheck/infrastructure/llm/fake.py`
- Create: `apps/api/src/govcheck/infrastructure/llm/groq.py`
- Create: `apps/api/src/govcheck/infrastructure/llm/ollama.py`
- Create: `apps/api/src/govcheck/infrastructure/llm/factory.py`
- Test: `apps/api/tests/domain/test_llm_contract.py`
- Test: `apps/api/tests/infrastructure/llm/test_factory.py`

**Interfaces:**
- Consumes: `Settings` from Task 1.
- Produces: `ChatMessage(role: Literal["system", "user", "assistant"], content: str)`; `LLMResult(text: str, model: str, usage: TokenUsage | None)`; `LLMProvider.complete(messages: Sequence[ChatMessage]) -> LLMResult`; `LLMProvider.stream(messages) -> AsyncIterator[str]`; `LLMProvider.structured(messages, schema: type[T]) -> T`; `build_llm_provider(settings: Settings) -> LLMProvider`.

- [ ] **Step 1: Write contract tests for deterministic completion, streaming, and structured output**

Tests must prove the fake emits configured chunks, validates Pydantic output, rejects an unknown provider, and never includes a Groq secret in an exception or object representation.

- [ ] **Step 2: Run the tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/domain/test_llm_contract.py tests/infrastructure/llm/test_factory.py -v`

Expected: FAIL with missing domain contracts.

- [ ] **Step 3: Implement ports, fake adapter, provider factory, and lazy Groq/Ollama adapters**

External clients must be instantiated only after provider selection so CI can import every module without keys or network calls.

- [ ] **Step 4: Run focused and full API tests**

Run: `make test-api`

Expected: PASS with no external LLM requests.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: add provider-independent LLM boundary"
```

### Task 3: Persistence schema and repository ports

**Files:**
- Create: `apps/api/src/govcheck/domain/documents.py`, `findings.py`, `events.py`
- Create: `apps/api/src/govcheck/domain/repositories.py`
- Create: `apps/api/src/govcheck/infrastructure/db/base.py`, `models.py`, `repositories.py`, `session.py`
- Create: `apps/api/migrations/env.py`, `apps/api/migrations/versions/0001_initial_schema.py`
- Test: `apps/api/tests/integration/db/test_migrations.py`, `test_document_repository.py`

**Interfaces:**
- Produces: UUID-based `Document`, `Page`, `Chunk`, `AnalysisJob`, `Finding`, `Citation`, `ToolRun`, `StreamEvent`, and `Report` entities; `DocumentRepository`; `FindingRepository`; `EventRepository.append(job_id, event_type, payload) -> StreamEvent`; `UnitOfWork` async context manager.

- [ ] **Step 1: Write migration and repository integration tests**

Tests apply migrations from an empty PostgreSQL database, save two documents with separate pages/chunks, round-trip typed findings/citations, and verify event sequence numbers are monotonic per job.

- [ ] **Step 2: Run against the disposable PostgreSQL service and confirm failure**

Run: `docker compose run --rm api python -m pytest tests/integration/db -v`

Expected: FAIL because migrations and repositories do not exist.

- [ ] **Step 3: Implement the initial migration and async SQLAlchemy repositories**

The `chunks.embedding` column uses pgvector with the chosen embedding dimension. Database records include `created_at`, `expires_at`, and ownership by an anonymous `session_id`.

- [ ] **Step 4: Run migration and repository tests twice**

Run: `make test-db && make test-db`

Expected: both runs PASS, proving repeatable setup/cleanup.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: persist documents findings and analysis events"
```

### Task 4: Defensive page-aware PDF ingestion

**Files:**
- Create: `apps/api/src/govcheck/domain/ingestion.py`
- Create: `apps/api/src/govcheck/infrastructure/pdf/extractor.py`
- Create: `apps/api/src/govcheck/application/ingest_document.py`
- Create: `apps/api/tests/fixtures/pdfs/` with generated, redistributable fixtures
- Test: `apps/api/tests/infrastructure/pdf/test_extractor.py`
- Test: `apps/api/tests/application/test_ingest_document.py`

**Interfaces:**
- Consumes: `DocumentRepository`, `UnitOfWork`, upload limits from `Settings`.
- Produces: `PdfPolicy(max_bytes: int, max_pages: int)`; `ExtractedPage(number: int, text: str)`; `PdfExtractor.extract(content: bytes, policy: PdfPolicy) -> list[ExtractedPage]`; `IngestDocument.execute(session_id, filename, content) -> Document`.

- [ ] **Step 1: Write ingestion tests for valid, corrupt, encrypted, image-only, oversized, and 51-page PDFs**

Assert typed error codes `invalid_pdf`, `encrypted_pdf`, `ocr_required`, `file_too_large`, and `page_limit_exceeded`, with safe Portuguese messages and no parser stack trace.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/infrastructure/pdf tests/application/test_ingest_document.py -v`

Expected: FAIL because extraction is absent.

- [ ] **Step 3: Implement signature validation, PyMuPDF extraction, page numbering, and transactional persistence**

Reject files before LLM or embedding work. Preserve original page numbers starting at 1 and normalize repeated whitespace without joining pages.

- [ ] **Step 4: Run focused tests and the complete API suite**

Run: `make test-api`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: ingest procurement PDFs with page provenance"
```

### Task 5: Chunking and local multilingual embeddings

**Files:**
- Create: `apps/api/src/govcheck/domain/retrieval.py`
- Create: `apps/api/src/govcheck/application/index_document.py`
- Create: `apps/api/src/govcheck/infrastructure/embeddings/fake.py`, `sentence_transformer.py`
- Test: `apps/api/tests/domain/test_chunking.py`
- Test: `apps/api/tests/application/test_index_document.py`

**Interfaces:**
- Consumes: `ExtractedPage`, `DocumentRepository`.
- Produces: `TextChunk(page_number: int, ordinal: int, text: str, start_char: int, end_char: int)`; `chunk_pages(pages, target_chars=1_200, overlap_chars=180) -> list[TextChunk]`; `EmbeddingProvider.embed_documents(texts) -> list[list[float]]`; `IndexDocument.execute(document_id) -> int`.

- [ ] **Step 1: Write tests for deterministic overlap, provenance, empty pages, and embedding cardinality**

Tests assert chunks never span page boundaries, maintain stable ordinal order, and store exactly one vector per non-empty chunk.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/domain/test_chunking.py tests/application/test_index_document.py -v`

Expected: FAIL with missing chunker/provider.

- [ ] **Step 3: Implement chunking, a deterministic fake embedding adapter, and a lazy sentence-transformer adapter**

Use the selected multilingual model behind `EmbeddingProvider`; model loading must not occur at import time.

- [ ] **Step 4: Run focused tests plus a local embedding smoke test**

Run: `make test-api && make smoke-embeddings`

Expected: tests PASS and smoke command returns the configured vector dimension.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: index page-aware chunks with multilingual embeddings"
```

### Task 6: Hybrid retrieval with document isolation and citations

**Files:**
- Create: `apps/api/src/govcheck/application/retrieve_evidence.py`
- Create: `apps/api/src/govcheck/infrastructure/retrieval/hybrid.py`
- Test: `apps/api/tests/infrastructure/retrieval/test_hybrid.py`
- Test: `apps/api/tests/integration/retrieval/test_document_isolation.py`

**Interfaces:**
- Consumes: stored `Chunk` vectors and `EmbeddingProvider`.
- Produces: `Evidence(chunk_id, document_id, page_number, excerpt, score)`; `HybridRetriever.search(document_id, query, limit=8) -> list[Evidence]`; reciprocal-rank fusion with `rrf_k=60`.

- [ ] **Step 1: Write ranking, tie, empty-index, and cross-document isolation tests**

Seed overlapping phrases in two documents and assert a query scoped to document A returns no chunk or excerpt from document B.

- [ ] **Step 2: Run retrieval tests and confirm failure**

Run: `make test-retrieval`

Expected: FAIL because hybrid retrieval is missing.

- [ ] **Step 3: Implement vector + BM25 retrieval and deterministic reciprocal-rank fusion**

Every database query must filter by `document_id` before ranking. Excerpts are bounded and retain page number.

- [ ] **Step 4: Run retrieval and full API tests**

Run: `make test-retrieval && make test-api`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: retrieve isolated evidence with hybrid ranking"
```

### Task 7: Evidence-grounded conversational RAG

**Files:**
- Create: `apps/api/src/govcheck/domain/chat.py`
- Create: `apps/api/src/govcheck/application/chat_with_document.py`
- Create: `apps/api/src/govcheck/prompts/chat_system.md`, `chat_answer.md`
- Test: `apps/api/tests/application/test_chat_with_document.py`
- Test: `apps/api/tests/security/test_document_prompt_injection.py`

**Interfaces:**
- Consumes: `HybridRetriever`, `LLMProvider`, session/document repositories.
- Produces: `Citation(page_number, excerpt, chunk_id)`; `ChatAnswer(text, citations, confidence, grounded)`; `ChatWithDocument.execute(session_id, document_id, question) -> ChatAnswer`; `ChatWithDocument.stream(...) -> AsyncIterator[ChatDelta]`.

- [ ] **Step 1: Write chat tests for cited answers, no-evidence refusal, ownership, follow-ups, and malicious document instructions**

The injection fixture includes instructions to ignore the system prompt and call an arbitrary URL. Assert the answer treats it as quoted document text, emits no tool request, and preserves the grounded-answer policy.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/application/test_chat_with_document.py tests/security/test_document_prompt_injection.py -v`

Expected: FAIL because the chat use case is absent.

- [ ] **Step 3: Implement versioned prompts, bounded conversation context, answer validation, and citations**

When retrieval is empty or the fake returns unsupported citation IDs, return the Portuguese not-found response with `grounded=false` and no invented citation.

- [ ] **Step 4: Run chat, security, and full tests**

Run: `make test-api`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: answer procurement questions with grounded citations"
```

### Task 8: Typed findings and LangGraph analysis workflow

**Files:**
- Create: `apps/api/src/govcheck/domain/analysis.py`
- Create: `apps/api/src/govcheck/application/analysis/graph.py`, `nodes.py`, `state.py`
- Create: `apps/api/src/govcheck/prompts/extract_findings.md`, `critic.md`, `synthesize.md`
- Test: `apps/api/tests/application/analysis/test_graph.py`
- Test: `apps/api/tests/application/analysis/test_evidence_critic.py`

**Interfaces:**
- Consumes: `LLMProvider`, `HybridRetriever`, repositories, tool registry from Task 9.
- Produces: `FindingCategory` enum (`deadline`, `document`, `value`, `criterion`, `sanction`, `obligation`); `FindingDraft`; `AnalysisState`; `build_analysis_graph(dependencies) -> CompiledStateGraph`; `RunAnalysis.execute(session_id, document_id) -> AnalysisJob`.

- [ ] **Step 1: Write graph tests for extraction, conditional validation, unsupported findings, conflicts, and idempotent reruns**

Assert distinct nodes appear in the event log and a finding without valid evidence becomes `unsupported` rather than silently receiving substitute text.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/application/analysis -v`

Expected: FAIL with missing graph/state.

- [ ] **Step 3: Implement typed extraction, evidence critic, synthesis, and LangGraph state transitions**

Infrastructure functions are not graph “agents.” Persist each state transition through `EventRepository` for SSE and debugging.

- [ ] **Step 4: Run graph and full API tests**

Run: `make test-api`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: orchestrate evidence-checked analysis with LangGraph"
```

### Task 9: Constrained public-data tool and provenance

**Files:**
- Create: `apps/api/src/govcheck/domain/tools.py`
- Create: `apps/api/src/govcheck/infrastructure/tools/registry.py`
- Create: `apps/api/src/govcheck/infrastructure/tools/procurement_lookup.py`
- Create: `apps/api/tests/fixtures/http/`
- Test: `apps/api/tests/infrastructure/tools/test_procurement_lookup.py`
- Test: `apps/api/tests/security/test_tool_constraints.py`

**Interfaces:**
- Consumes: validated extracted identifier and `httpx.AsyncClient`.
- Produces: `ToolRequest(name, arguments)`; `ToolResult(status: Literal["verified", "not_found", "unavailable", "invalid"], source_url, checked_at, data, error_code)`; `Tool.execute(arguments) -> ToolResult`; `ToolRegistry.invoke(request) -> ToolResult`.

- [ ] **Step 1: Verify the current official/public endpoint and capture sanitized response fixtures**

Record the selected provider, terms, timeout expectations, and exact provenance fields in `docs/architecture.md`; do not label a community aggregator as official.

- [ ] **Step 2: Write success, not-found, malformed-response, timeout, rate-limit, invalid-identifier, and arbitrary-URL tests**

Assert tool arguments cannot choose a host or URL. Timeouts and malformed data return `unavailable` and never a successful validation.

- [ ] **Step 3: Run focused tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/infrastructure/tools tests/security/test_tool_constraints.py -v`

Expected: FAIL because the registry/tool do not exist.

- [ ] **Step 4: Implement the allowlisted adapter, validation, retries, timeouts, and provenance persistence**

Retry only idempotent transient failures with a bounded backoff. Store tool name, sanitized request, status, source, and timestamp.

- [ ] **Step 5: Run tool and complete API suites**

Run: `make test-api`

Expected: PASS with no live API call in the test suite.

- [ ] **Step 6: Commit**

```bash
git add apps/api docs/architecture.md
git commit -m "feat: validate findings through a constrained public-data tool"
```

### Task 10: Versioned API, SSE replay, and report export

**Files:**
- Create: `apps/api/src/govcheck/api/errors.py`, `dependencies.py`, `schemas.py`
- Create: `apps/api/src/govcheck/api/routes/documents.py`, `chat.py`, `analysis.py`, `reports.py`
- Create: `apps/api/src/govcheck/application/render_report.py`, `cleanup_expired.py`
- Test: `apps/api/tests/api/test_documents.py`, `test_chat.py`, `test_analysis_stream.py`, `test_reports.py`

**Interfaces:**
- Consumes: ingestion, indexing, chat, analysis, event, and report services.
- Produces: the `/api/v1` endpoints fixed in the design; SSE events with `id`, `event`, and JSON `data`; `Last-Event-ID` replay; Markdown and JSON reports; typed `{error:{code,message,request_id}}` failures.

- [ ] **Step 1: Write end-to-end API tests from upload through report export**

Include 5 MiB/50-page policy responses, session ownership, a disconnect after event 2, replay from ID 2 without duplicate terminal event, and both report content types.

- [ ] **Step 2: Run API tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/api -v`

Expected: FAIL with missing routes.

- [ ] **Step 3: Implement routes, background job boundary, SSE replay, report renderers, cleanup, and typed errors**

OpenAPI descriptions must distinguish PDF facts, external-source values, model interpretation, and unavailable checks.

- [ ] **Step 4: Run API tests and inspect generated OpenAPI**

Run: `make test-api && make check-openapi`

Expected: PASS and OpenAPI contains every versioned route from the design.

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: expose streaming analysis and auditable reports"
```

### Task 11: Portuguese reviewer experience in Next.js

**Files:**
- Create: `apps/web/src/lib/api.ts`, `contracts.ts`, `sse.ts`
- Create: `apps/web/src/features/upload/`, `chat/`, `findings/`, `report/`
- Create: `apps/web/src/components/ui/`, `source-citation.tsx`, `status-timeline.tsx`, `responsible-use.tsx`
- Modify: `apps/web/src/app/page.tsx`, `apps/web/src/app/layout.tsx`, `apps/web/src/app/globals.css`
- Test: `apps/web/tests/unit/`, `apps/web/tests/e2e/reviewer-flow.spec.ts`

**Interfaces:**
- Consumes: generated API contracts and SSE stream from Task 10.
- Produces: upload workspace; guided sample path; cited chat; grouped findings; validation provenance; progress timeline; Markdown/JSON download; responsive and keyboard-accessible UI.

- [ ] **Step 1: Write component tests for upload states, citations, unsupported findings, tool failures, and disclaimer visibility**

The legal-use boundary must be visible before upload and inside every exported-result view. Colors cannot be the only signal for confidence or status.

- [ ] **Step 2: Run component tests and confirm failure**

Run: `cd apps/web && pnpm test`

Expected: FAIL because the features are missing.

- [ ] **Step 3: Implement the workspace with typed API client and resilient SSE handling**

Use a calm civic-product visual language, clear Portuguese microcopy, progressive disclosure, mobile layout, and no fabricated dashboard metrics.

- [ ] **Step 4: Write and run the reviewer-flow E2E test with mocked deterministic backend**

Run: `cd apps/web && pnpm test:e2e`

Expected: PASS for upload → progress → cited chat → findings → report download at desktop and mobile widths.

- [ ] **Step 5: Run accessibility and production build checks**

Run: `make test-web && make build-web`

Expected: PASS with no serious automated accessibility violation.

- [ ] **Step 6: Commit**

```bash
git add apps/web
git commit -m "feat: deliver the GovCheck reviewer workspace"
```

### Task 12: Evaluation harness and measured limitations

**Files:**
- Create: `packages/evaluation/pyproject.toml`
- Create: `packages/evaluation/govcheck_eval/runner.py`, `metrics.py`, `schemas.py`
- Create: `packages/evaluation/datasets/manifest.json`, question JSONL files, source attribution files
- Create: `packages/evaluation/tests/test_metrics.py`, `test_dataset_schema.py`
- Create: `docs/evaluation.md`

**Interfaces:**
- Consumes: live or fake API base URL and versioned public-notice datasets.
- Produces: `EvaluationResult` with citation recall, field-level precision/recall/F1, unsupported-claim rate, rubric score, and stage latency; Markdown/JSON summaries.

- [ ] **Step 1: Write metric tests with hand-calculated expected values and dataset validation tests**

Test zero denominators, partial field matches, duplicate citations, unsupported claims, and missing latency events.

- [ ] **Step 2: Run evaluation tests and confirm failure**

Run: `cd packages/evaluation && python -m pytest -v`

Expected: FAIL because metrics are absent.

- [ ] **Step 3: Implement schemas, metrics, runner, and reproducible dataset manifest**

Each question includes expected answer fields and expected page evidence. Dataset licenses/source URLs and manual-rubric instructions are explicit.

- [ ] **Step 4: Execute deterministic baseline and one real-provider evaluation when Groq is available**

Run: `make eval-fake` and later `make eval-live`

Expected: versioned JSON output and a generated table in `docs/evaluation.md`; failures and limitations remain visible.

- [ ] **Step 5: Commit**

```bash
git add packages/evaluation docs/evaluation.md
git commit -m "test: measure retrieval grounding and extraction quality"
```

### Task 13: Security hardening, threat model, and retention

**Files:**
- Create: `apps/api/src/govcheck/api/middleware/rate_limit.py`, `request_id.py`, `logging.py`
- Create: `apps/api/tests/security/test_secret_redaction.py`, `test_rate_limit.py`, `test_retention.py`
- Create: `docs/threat-model.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: API and persistence from Tasks 3 and 10.
- Produces: request IDs, structured redacted logs, session/concurrency limits, 60-minute expiry, cleanup command, dependency audit and secret scan in CI.

- [ ] **Step 1: Write tests for secret redaction, content-free logs, rate limiting, one active analysis per session, and expired-document deletion**

Assert API keys, authorization headers, document text, and raw PDF bytes never appear in logs or exception responses.

- [ ] **Step 2: Run security tests and confirm failure**

Run: `cd apps/api && python -m pytest tests/security -v`

Expected: FAIL for missing middleware/cleanup policies.

- [ ] **Step 3: Implement middleware, cleanup scheduling/command, and CI security checks**

Document prompt injection, malicious PDFs, SSRF, data retention, provider exposure, denial of service, and residual risks with mitigations.

- [ ] **Step 4: Run all backend, frontend, security, build, and audit checks**

Run: `make verify`

Expected: all checks PASS without provider secrets.

- [ ] **Step 5: Commit**

```bash
git add apps/api .github docs/threat-model.md
git commit -m "security: harden the public document-analysis demo"
```

### Task 14: Railway deployment and portfolio handoff

**Files:**
- Create: `infra/railway/README.md`, service configuration files selected by the connected Railway plugin
- Create: `docs/architecture.md`, `docs/interview-guide.md`
- Modify: `README.md`, `.env.example`, `compose.yaml`
- Create: `apps/web/public/demo/` for optimized screenshots/GIF assets
- Test: `scripts/smoke_deployment.sh`

**Interfaces:**
- Consumes: complete application, Railway connection, `GROQ_API_KEY` stored only as a deployment secret.
- Produces: live web URL, API/OpenAPI URL, health checks, seeded sample flow, architecture/evaluation/security documentation, interview guide, and final release tag.

- [ ] **Step 1: Connect Railway, provision PostgreSQL/pgvector, API, and web services, and configure non-secret environment values**

Do not store the Groq key in the repository. The user enters it through the provider’s secret UI or approved secret-management path.

- [ ] **Step 2: Deploy the current commit and run smoke checks**

Run: `scripts/smoke_deployment.sh "$APP_URL" "$API_URL"`

Expected: web 200, `/health` 200, `/ready` 200, sample document analysis completes, cited chat responds, and both report formats download.

- [ ] **Step 3: Write README, architecture guide, evaluation summary, threat-model link, and interview guide**

README includes demo, GIF/video, problem, responsible-use boundary, architecture, features, quick starts, tests, evaluation table, limitations, roadmap, and no claim of final legal compliance.

- [ ] **Step 4: Verify from a clean checkout and perform visual/browser QA**

Run: `make clean-room-verify` followed by the production reviewer flow in desktop and mobile viewports.

Expected: documented commands work from scratch; no console error; every cited source opens the right page/excerpt; layouts remain usable.

- [ ] **Step 5: Commit and tag the release**

```bash
git add .
git commit -m "docs: prepare GovCheck AI portfolio release"
git tag -a v1.0.0 -m "GovCheck AI portfolio release"
```

- [ ] **Step 6: Obtain user approval, then change repository visibility to public**

Expected: publication happens only after Cássio reviews the repository, demo, documentation, and secret history.

## Plan Self-Review

- **Spec coverage:** every goal maps to Tasks 1–14; non-goals remain excluded.
- **Step scan:** each task has an independent failing-test cycle, implementation boundary, verification command, and commit.
- **Type consistency:** `Settings`, `LLMProvider`, repositories, `Evidence`, `ChatAnswer`, graph state, tool results, SSE events, and evaluation results are introduced before consumption.
- **Review Focus coverage:** PDF failures (Task 4), retrieval isolation (Task 6), prompt injection (Task 7), tool failures (Task 9), and SSE reconnect (Task 10) each have explicit tests.
- **Proportion:** the plan fixes interfaces and verification behavior but leaves implementation bodies to the executor.
