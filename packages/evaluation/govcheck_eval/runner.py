import argparse
import asyncio
import hashlib
import json
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from govcheck_eval.metrics import evaluate, normalize_label
from govcheck_eval.schemas import (
    DatasetDocument,
    EvaluationDataset,
    EvaluationResult,
    FindingPrediction,
    PredictionBundle,
    QuestionPrediction,
    StageLatencySample,
    load_dataset,
)

EVENT_TO_STAGE = {
    "analysis.extraction.completed": "extraction",
    "analysis.external_validation.completed": "external_validation",
    "analysis.external_validation.skipped": "external_validation",
    "analysis.evidence_critic.completed": "evidence_critic",
    "analysis.synthesis.completed": "synthesis",
}


def _percent(value: float | None) -> str:
    return "pendente" if value is None else f"{value * 100:.1f}%"


def render_markdown(dataset: EvaluationDataset, result: EvaluationResult) -> str:
    source_rows = "\n".join(
        (
            f"| {document.title} | [{document.attribution.publisher}]"
            f"({document.attribution.source_url}) | {document.attribution.license_name} |"
        )
        for document in dataset.documents
    )
    latency_rows = "\n".join(
        (
            f"| `{stage}` | {stats.count} | {stats.p50_ms:.1f} | "
            f"{stats.p95_ms:.1f} | {stats.mean_ms:.1f} |"
        )
        for stage, stats in result.latency.stages.items()
    )
    limitations = "\n".join(f"- {item}" for item in result.limitations) or "- Nenhuma registrada."
    generated_at = result.evaluated_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    baseline_note = (
        "O provedor `deterministic-contract-fixture` é uma linha de base de contrato com "
        "falhas intencionais; demonstra que o avaliador penaliza erros, mas **não** representa "
        "desempenho de GPT, Llama, Mistral, Groq ou Ollama. Uma execução real deve ser "
        "registrada separadamente e manter os casos falhos."
        if result.provider == "deterministic-contract-fixture"
        else "Esta é uma execução ao vivo; o identificador do provedor foi informado pelo operador "
        "e as avaliações manuais pendentes devem ser concluídas antes de comparar modelos."
    )
    return f"""# Avaliação do GovCheck AI

> Avaliação técnica; não mede conformidade jurídica e não substitui revisão humana.

## Resultado versionado

| Execução | Dataset | Provedor | Documentos | Perguntas | Campos esperados |
|---|---|---|---:|---:|---:|
| `{result.run_id}` | `{result.dataset_version}` | `{result.provider}` | {result.document_count} | {result.question_count} | {result.finding_count} |

| Métrica | Resultado | Definição |
|---|---:|---|
| Recall de citação | {_percent(result.citation_recall)} | Páginas esperadas recuperadas; citações duplicadas contam uma vez por pergunta. |
| Precisão de campos | {_percent(result.fields.precision)} | Valores extraídos corretos / todos os valores extraídos. |
| Recall de campos | {_percent(result.fields.recall)} | Valores esperados recuperados / todos os valores esperados. |
| F1 de campos | {_percent(result.fields.f1)} | Média harmônica entre precisão e recall de campos. |
| Alegações sem suporte | {_percent(result.unsupported_claim_rate if result.claims_assessed else None)} | {result.unsupported_claims} de {result.claims_assessed} alegações manualmente avaliadas. |
| Rubrica de resposta | {_percent(result.rubric.normalized_score)} | {result.rubric.scored_cases} avaliadas; {result.rubric.pending_cases} pendentes. |

Gerado em `{generated_at}`.

## Latência observada por estágio

| Estágio | Amostras | p50 (ms) | p95 (ms) | média (ms) |
|---|---:|---:|---:|---:|
{latency_rows}

Eventos ausentes: **{result.latency.missing_events}/{result.latency.expected_events}**. Ausência permanece visível e não é convertida em zero.

## Dataset e proveniência

O conjunto contém 15 perguntas e 15 campos rotulados sobre três editais públicos com PDF textual. Os binários não são redistribuídos: o avaliador espera que sejam baixados das fontes oficiais com os nomes indicados no manifesto e rejeita conteúdo cujo SHA-256 difira do snapshot rotulado.

| Documento | Fonte oficial | Licença/uso |
|---|---|---|
{source_rows}

As páginas são 1-based no PDF. Cada rótulo registra páginas esperadas; fatos repetidos foram associados à página canônica mais curta que os sustenta.

## Metodologia

- **Recall de citação:** micro-média sobre páginas esperadas por pergunta. Uma página repetida não aumenta o resultado.
- **Campos:** pareamento por documento, categoria, identificador semântico versionado (ou alias aceito) e valor normalizado. Campo ou valor incorreto gera simultaneamente falso positivo e falso negativo.
- **Alegações sem suporte:** revisão manual da atomicidade factual; sem alegações avaliadas, a métrica permanece pendente (`null`) em vez de exibir 0%.
- **Rubrica (0–4):** os quatro itens de cada pergunta valem um ponto. Execuções ao vivo nascem pendentes para impedir autoavaliação pelo próprio modelo.
- **Latência:** a indexação usa tempo de parede do cliente, incluindo upload e rede; os estágios da análise usam timestamps persistidos pelo servidor, evitando distorção por polling ou replay SSE.

## Limitações desta execução

{limitations}

{baseline_note}

## Como reproduzir

```bash
make install
make eval-test
make eval-fake
```

Para uma execução real, baixe os três PDFs oficiais para um diretório usando os nomes de `datasets/manifest.json`, inicie a API com um provedor configurado e rode:

```bash
make eval-live EVAL_API_BASE_URL=http://localhost:8000 EVAL_DOCUMENTS_DIR=/caminho/para/pdfs EVAL_PROVIDER=groq:openai/gpt-oss-120b
```

O comando ao vivo salva as previsões brutas. Preencha `rubric_score`, `claims_total` e `claims_unsupported` após revisão humana e execute o subcomando `score` para publicar o resultado final.
"""


def _write_result(
    dataset: EvaluationDataset,
    result: EvaluationResult,
    *,
    output: Path,
    markdown_output: Path | None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(dataset, result), encoding="utf-8")


def score_predictions(
    *,
    dataset_dir: Path,
    predictions_path: Path,
    output: Path,
    markdown_output: Path | None,
) -> EvaluationResult:
    dataset = load_dataset(dataset_dir)
    predictions = PredictionBundle.model_validate_json(
        predictions_path.read_text(encoding="utf-8")
    )
    result = evaluate(dataset, predictions)
    _write_result(dataset, result, output=output, markdown_output=markdown_output)
    return result


def _parse_sse(payload: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in payload.replace("\r\n", "\n").split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line or line.startswith(":"):
                continue
            name, value = line.split(":", 1)
            fields[name] = value.lstrip()
        if not {"id", "event", "data"} <= fields.keys():
            continue
        events.append(
            {
                "id": int(fields["id"]),
                "event": fields["event"],
                "data": json.loads(fields["data"]),
            }
        )
    return events


def _event_timestamp(event: dict[str, Any]) -> datetime:
    data = event.get("data")
    value = data.get("recorded_at") if isinstance(data, dict) else None
    if not isinstance(value, str):
        raise TypeError("analysis event is missing recorded_at")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("analysis event recorded_at must include a timezone")
    return parsed.astimezone(UTC)


def _latencies_from_events(
    events: list[dict[str, Any]],
    dataset_document_id: str,
) -> list[StageLatencySample]:
    started_at: datetime | None = None
    boundary_at: datetime | None = None
    samples: list[StageLatencySample] = []
    for event in sorted(events, key=lambda item: int(item["id"])):
        recorded_at = _event_timestamp(event)
        event_name = event["event"]
        if event_name == "analysis.started":
            started_at = recorded_at
            boundary_at = recorded_at
            continue
        if stage := EVENT_TO_STAGE.get(event_name):
            if boundary_at is None:
                raise ValueError("analysis stage was recorded before analysis.started")
            milliseconds = (recorded_at - boundary_at).total_seconds() * 1000
            if milliseconds < 0:
                raise ValueError("analysis event timestamps are not monotonic")
            samples.append(
                StageLatencySample(
                    document_id=dataset_document_id,
                    stage=stage,
                    milliseconds=milliseconds,
                )
            )
            boundary_at = recorded_at
        if event_name == "analysis.completed":
            if started_at is None:
                raise ValueError("analysis.completed was recorded before analysis.started")
            total_ms = (recorded_at - started_at).total_seconds() * 1000
            if total_ms < 0:
                raise ValueError("analysis event timestamps are not monotonic")
            samples.append(
                StageLatencySample(
                    document_id=dataset_document_id,
                    stage="total",
                    milliseconds=total_ms,
                )
            )
    return samples


def _verify_document_bytes(
    document: DatasetDocument,
    pdf_bytes: bytes,
    pdf_path: Path,
) -> None:
    actual_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    if document.sha256 and actual_sha256 != document.sha256:
        raise ValueError(
            f"SHA-256 mismatch for {pdf_path}: expected {document.sha256}, got {actual_sha256}"
        )


def _canonical_field(
    dataset: EvaluationDataset,
    *,
    document_id: str,
    category: str,
    title: str,
) -> str:
    normalized_title = normalize_label(title)
    matches = [
        case.field
        for case in dataset.findings
        if case.document_id == document_id
        and case.category == category
        and normalized_title
        in {
            normalize_label(case.field),
            *(normalize_label(alias) for alias in case.field_aliases),
        }
    ]
    return matches[0] if len(matches) == 1 else title


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    detail = response.text[:500].replace("\n", " ")
    raise RuntimeError(f"GovCheck API returned {response.status_code}: {detail}")


async def _observe_analysis(
    client: httpx.AsyncClient,
    document_id: str,
    dataset_document_id: str,
    *,
    timeout_seconds: float,
) -> list[StageLatencySample]:
    started = time.perf_counter()
    last_event_id = 0
    events: list[dict[str, Any]] = []
    while time.perf_counter() - started < timeout_seconds:
        response = await client.get(
            f"/api/v1/documents/{document_id}/events",
            headers={"Last-Event-ID": str(last_event_id)},
        )
        _raise_for_status(response)
        for event in _parse_sse(response.text):
            if event["id"] <= last_event_id:
                continue
            last_event_id = event["id"]
            events.append(event)
            if event["event"] == "analysis.failed":
                raise RuntimeError(f"analysis failed for {dataset_document_id}")
            if event["event"] == "analysis.completed":
                return _latencies_from_events(events, dataset_document_id)
        await asyncio.sleep(0.25)
    raise TimeoutError(f"analysis timed out for {dataset_document_id}")


async def collect_live_predictions(
    dataset: EvaluationDataset,
    *,
    api_base_url: str,
    documents_dir: Path,
    session_id: str,
    provider: str,
    timeout_seconds: float,
) -> PredictionBundle:
    headers = {"X-Session-ID": session_id}
    question_predictions: list[QuestionPrediction] = []
    finding_predictions: list[FindingPrediction] = []
    latencies: list[StageLatencySample] = []
    questions_by_document: dict[str, list[Any]] = {}
    for question in dataset.questions:
        questions_by_document.setdefault(question.document_id, []).append(question)

    async with httpx.AsyncClient(
        base_url=api_base_url.rstrip("/"),
        headers=headers,
        timeout=httpx.Timeout(timeout_seconds),
    ) as client:
        for document in dataset.documents:
            pdf_path = documents_dir / document.local_filename
            if not pdf_path.is_file():
                raise FileNotFoundError(
                    f"missing {pdf_path}; download it from {document.attribution.source_url}"
                )
            pdf_bytes = pdf_path.read_bytes()
            _verify_document_bytes(document, pdf_bytes, pdf_path)
            indexing_started = time.perf_counter()
            response = await client.post(
                "/api/v1/documents",
                files={"file": (document.local_filename, pdf_bytes, "application/pdf")},
            )
            _raise_for_status(response)
            uploaded = response.json()
            latencies.append(
                StageLatencySample(
                    document_id=document.id,
                    stage="indexing",
                    milliseconds=(time.perf_counter() - indexing_started) * 1000,
                )
            )
            document_id = uploaded["id"]
            response = await client.post(f"/api/v1/documents/{document_id}/analysis")
            _raise_for_status(response)
            latencies.extend(
                await _observe_analysis(
                    client,
                    document_id,
                    document.id,
                    timeout_seconds=timeout_seconds,
                )
            )
            response = await client.get(f"/api/v1/documents/{document_id}/findings")
            _raise_for_status(response)
            for item in response.json():
                finding_predictions.append(
                    FindingPrediction(
                        document_id=document.id,
                        category=item["category"],
                        field=_canonical_field(
                            dataset,
                            document_id=document.id,
                            category=item["category"],
                            title=item["title"],
                        ),
                        value=item["value"],
                        cited_pages=[citation["page_number"] for citation in item["citations"]],
                    )
                )
            for question in questions_by_document.get(document.id, []):
                question_started = time.perf_counter()
                response = await client.post(
                    f"/api/v1/documents/{document_id}/chat",
                    json={"question": question.question},
                )
                _raise_for_status(response)
                item = response.json()
                question_predictions.append(
                    QuestionPrediction(
                        question_id=question.id,
                        answer=item["text"],
                        cited_pages=[citation["page_number"] for citation in item["citations"]],
                        claims_total=0,
                        claims_unsupported=0,
                        rubric_score=None,
                        latency_ms=(time.perf_counter() - question_started) * 1000,
                    )
                )
    return PredictionBundle(
        dataset_version=dataset.version,
        run_id=f"live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        provider=provider,
        created_at=datetime.now(UTC),
        questions=question_predictions,
        findings=finding_predictions,
        latencies=latencies,
        notes=[
            "Execução ao vivo: rubrica e alegações aguardam revisão humana independente.",
            "Indexação inclui upload/rede; estágios da análise usam timestamps do servidor.",
        ],
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate GovCheck AI grounding and extraction")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="score a versioned prediction bundle")
    score.add_argument("--dataset-dir", type=Path, required=True)
    score.add_argument("--predictions", type=Path, required=True)
    _add_output_arguments(score)

    live = subparsers.add_parser("live", help="collect predictions from a running GovCheck API")
    live.add_argument("--dataset-dir", type=Path, required=True)
    live.add_argument("--api-base-url", required=True)
    live.add_argument("--documents-dir", type=Path, required=True)
    live.add_argument("--session-id", default=f"eval-{uuid4()}")
    live.add_argument("--provider", required=True)
    live.add_argument("--timeout-seconds", type=float, default=300)
    live.add_argument("--predictions-output", type=Path, required=True)
    _add_output_arguments(live)
    return parser


def main(argv: Iterable[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "score":
        result = score_predictions(
            dataset_dir=args.dataset_dir,
            predictions_path=args.predictions,
            output=args.output,
            markdown_output=args.markdown_output,
        )
    else:
        dataset = load_dataset(args.dataset_dir)
        predictions = asyncio.run(
            collect_live_predictions(
                dataset,
                api_base_url=args.api_base_url,
                documents_dir=args.documents_dir,
                session_id=args.session_id,
                provider=args.provider,
                timeout_seconds=args.timeout_seconds,
            )
        )
        args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
        args.predictions_output.write_text(
            predictions.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        result = evaluate(dataset, predictions)
        _write_result(
            dataset,
            result,
            output=args.output,
            markdown_output=args.markdown_output,
        )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "citation_recall": result.citation_recall,
                "field_f1": result.fields.f1,
                "unsupported_claim_rate": result.unsupported_claim_rate,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
