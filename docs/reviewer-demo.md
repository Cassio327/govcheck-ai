# GovCheck AI — reviewer demonstration

This document is a reproducible guide for someone evaluating the repository.
It distinguishes interface fixtures, automated tests, and real-model behavior.

**Start here:** [watch the published 2m06s captioned demo](media/govcheck-ai-demo-legendado.mp4) →
[walkthrough and limitations](demo.md) → [system architecture](architecture.md) →
[evaluation methodology](evaluation.md).
The demonstration video is published in this repository; it is **not** a hosted
application and does not constitute an LLM quality benchmark.

## 1. Inspect the system without credentials (2 minutes)

1. Run `docker compose up --build` from the repository root.
2. Open `http://localhost:3000`.
3. Click **Usar edital de exemplo**.
4. Filter the example findings by category; expand one citation and inspect
   the page number, evidence status, and confidence.
5. Ask **Qual é o prazo?** and download the Markdown or JSON report.

**What this proves:** the Next.js interaction design and the downloadable
example report. All example findings and answers are **fictional, in-memory
UI fixtures**. This does **not** run the real PDF analysis or claim AI accuracy.

## 2. Inspect the real pipeline with a public PDF

Prerequisites: a text-searchable, publicly accessible edital PDF, a configured
real LLM provider, and enough resources for optional real embeddings.

For local Ollama, from the repository root:

```bash
export LLM_PROVIDER=ollama
export EMBEDDING_PROVIDER=sentence-transformer
export INSTALL_EMBEDDINGS=true
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull llama3.2:3b
```

For hosted Groq, configure `LLM_PROVIDER=groq` and `GROQ_API_KEY`
privately. Do not commit keys or upload confidential materials. With Groq,
real sentence-transformer embeddings remain optional via the two
`EMBEDDING_*`/`INSTALL_EMBEDDINGS` settings.

After the model is installed and services are healthy:

1. Upload one small, text-based public edital (maximum 5 MiB / 50 pages).
2. Observe the extraction, external validation when applicable, evidence
   criticism, and synthesis events.
3. Open at least three findings: one deadline, one qualification requirement,
   and one sanction or criterion.
4. Check each claim against the **actual cited PDF page**; do not equate
   citation-ID validity with legal correctness.
5. Ask a question that can be answered from the PDF, then one that cannot.
6. Export the report and review unsupported/conflicting claims explicitly.

**What this evaluates:** an actual provider-driven pipeline. Quality depends
on the chosen model, prompt, document and embedding configuration. No live
benchmark result is currently claimed in this repository.

## 3. Reproduce automated engineering checks

```bash
make install
make verify
```

GitHub Actions additionally tests PostgreSQL migrations, browser E2E flows,
accessibility, dependency/secret scanning, and container builds. Browser E2E
tests mock the HTTP API and cannot substitute for provider integration tests.
See `docs/evaluation.md` for reproducible fixture scoring and the separate
live-evaluation procedure.

## 4. What to explain in an interview

- **Problem:** public procurement documents are long; ungrounded summaries
  can omit critical clauses or invent information.
- **Architecture:** FastAPI API, isolated PDF chunks, hybrid BM25 + semantic
  retrieval, bounded LangGraph analysis, allowlisted PNCP tool, critic and
  auditable Markdown/JSON outputs.
- **Engineering choice:** six category-focused retrieval queries give
  different edital sections a chance to appear in the model context, while
  a cap of 20 unique source chunks controls context growth.
- **Safety boundaries:** anonymous session isolation, limited document
  retention, restricted tool inputs, explicit unsupported/conflicting states,
  and a required human review.
- **Tradeoffs:** pgvector currently stores vectors, but ranking is done in
  application memory; scanned PDFs need OCR; there is no authenticated
  multi-tenant production deployment; tested fixture scores are not real
  model accuracy.
- **Next experiment:** benchmark one pinned real model and embedding
  configuration against the labeled public-edital dataset, record failures,
  and report quality/latency alongside the existing deterministic baseline.

## 5. Release checklist

- [ ] Verify latest GitHub Actions run is green
- [ ] Test real model on more than one official, text-based edital
- [ ] Record selected model/version, provider, dataset and evaluation date
- [ ] Confirm citations manually and document failure cases
- [ ] Capture a short screenshot/video using **clearly labeled** example
      fixtures or verified live outputs
- [ ] Remove secrets/test data and verify the intended public-facing wording
- [ ] Publish repository only after the owner approves disclosure
