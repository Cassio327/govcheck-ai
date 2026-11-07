# GovCheck AI — Architecture Notes

## Product boundary

GovCheck AI performs preliminary, evidence-grounded reading of Brazilian public procurement
documents. It does not issue a legal opinion or certify compliance. Document text is always treated
as untrusted data, and every factual result must retain a page-level citation or an explicit
`unsupported`/`conflicting` status.

## Analysis flow

```mermaid
flowchart TD
    PDF[PDF ingestion] --> IDX[Page-aware indexing]
    IDX --> RET[Hybrid retrieval]
    RET --> EXT[Typed extraction]
    EXT --> VAL[Allowlisted validation]
    VAL --> CRT[Evidence critic]
    CRT --> SYN[Auditable synthesis]
```

The analysis workflow is a typed LangGraph state machine. Extraction, external validation,
evidence criticism, and synthesis are separate nodes. PDF parsing, persistence, API transport, and
SSE delivery remain infrastructure rather than being presented as “agents.” Each node appends a
monotonic event for replay and debugging.

## Official external source: PNCP

Checked on 3 November 2026 against the official [PNCP consultation Swagger](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
and [PNCP Integration Manual](https://pncp.gov.br/manual/pt-br/latest/singlehtml/).

The first production tool validates a PNCP procurement control number with the public consultation
endpoint:

```text
GET https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
```

The official control-number mask for a procurement is
`99999999999999-1-999999/9999`. The adapter decomposes that identifier locally and never accepts a
host, URL, path, method, or headers from model output. The returned `numeroControlePNCP` must equal
the requested identifier before the result can be marked `verified`.

Only these response fields may be persisted:

- `numeroControlePNCP`, `numeroCompra`, `anoCompra`, and `processo`;
- `objetoCompra`, `modalidadeNome`, and `situacaoCompraNome`;
- `dataAberturaProposta` and `dataEncerramentoProposta`.

Every execution stores the fixed tool name, sanitized identifier, status, source URL, timestamp,
whitelisted response, and stable error code. `404` becomes `not_found`; malformed payloads,
timeouts, rate limits, and upstream failures never become successful validations. Only transient,
idempotent GET failures receive one bounded retry.

Tests use a sanitized fixture derived from the documented response contract and make no live PNCP
request. This keeps CI deterministic while the source and check date remain explicit.
