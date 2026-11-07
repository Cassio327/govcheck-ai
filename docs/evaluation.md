# Avaliação do GovCheck AI

> Avaliação técnica; não mede conformidade jurídica e não substitui revisão humana.

## Resultado versionado

| Execução | Dataset | Provedor | Documentos | Perguntas | Campos esperados |
|---|---|---|---:|---:|---:|
| `fake-baseline-2026-11-07` | `2026.11.1` | `deterministic-contract-fixture` | 3 | 15 | 15 |

| Métrica | Resultado | Definição |
|---|---:|---|
| Recall de citação | 86.7% | Páginas esperadas recuperadas; citações duplicadas contam uma vez por pergunta. |
| Precisão de campos | 86.7% | Valores extraídos corretos / todos os valores extraídos. |
| Recall de campos | 86.7% | Valores esperados recuperados / todos os valores esperados. |
| F1 de campos | 86.7% | Média harmônica entre precisão e recall de campos. |
| Alegações sem suporte | 13.3% | 2 de 15 alegações manualmente avaliadas. |
| Rubrica de resposta | 90.0% | 15 avaliadas; 0 pendentes. |

Gerado em `2026-11-07T00:00:00Z`.

## Latência observada por estágio

| Estágio | Amostras | p50 (ms) | p95 (ms) | média (ms) |
|---|---:|---:|---:|---:|
| `indexing` | 3 | 150.0 | 177.0 | 150.0 |
| `extraction` | 3 | 280.0 | 316.0 | 280.0 |
| `external_validation` | 2 | 22.5 | 24.8 | 22.5 |
| `evidence_critic` | 3 | 150.0 | 159.0 | 150.0 |
| `synthesis` | 3 | 65.0 | 69.5 | 65.0 |
| `total` | 3 | 665.0 | 746.0 | 666.7 |

Eventos ausentes: **1/18**. Ausência permanece visível e não é convertida em zero.

## Dataset e proveniência

O conjunto contém 15 perguntas e 15 campos rotulados sobre três editais públicos com PDF textual. Os binários não são redistribuídos: o avaliador espera que sejam baixados das fontes oficiais com os nomes indicados no manifesto e rejeita conteúdo cujo SHA-256 difira do snapshot rotulado.

| Documento | Fonte oficial | Licença/uso |
|---|---|---|
| UFPE — Pregão Eletrônico 90001/2024 — outsourcing de impressão | [Universidade Federal de Pernambuco (UFPE)](https://www.ufpe.br/documents/5353690/5365278/Edital-reabertura-90001.2024.pdf/9d9b4f5a-e70c-444c-82c6-9e27eef1929c) | Licença de redistribuição não declarada; documento usado somente por referência |
| UnirG — Pregão Eletrônico SRP 014/2024 — materiais e equipamentos de TIC | [Fundação Universidade de Gurupi (UnirG)](https://unitransparencia.unirg.edu.br/storage/unitransparencia/edital-pregao-eletronico/edital_-_material_de_tic_-_assinado.pdf) | Licença de redistribuição não declarada; documento usado somente por referência |
| Polícia Federal/BA — Pregão Eletrônico 002/2023 — suporte de TIC | [Polícia Federal — Superintendência Regional na Bahia](https://www.gov.br/pf/pt-br/assuntos/licitacoes/2023/bahia/pregao-eletronico/doc-unico-publicacao-2.pdf/@@download/file) | Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada |

As páginas são 1-based no PDF. Cada rótulo registra páginas esperadas; fatos repetidos foram associados à página canônica mais curta que os sustenta.

## Metodologia

- **Recall de citação:** micro-média sobre páginas esperadas por pergunta. Uma página repetida não aumenta o resultado.
- **Campos:** pareamento por documento, categoria, identificador semântico versionado (ou alias aceito) e valor normalizado. Campo ou valor incorreto gera simultaneamente falso positivo e falso negativo.
- **Alegações sem suporte:** revisão manual da atomicidade factual; sem alegações avaliadas, a métrica permanece pendente (`null`) em vez de exibir 0%.
- **Rubrica (0–4):** os quatro itens de cada pergunta valem um ponto. Execuções ao vivo nascem pendentes para impedir autoavaliação pelo próprio modelo.
- **Latência:** a indexação usa tempo de parede do cliente, incluindo upload e rede; os estágios da análise usam timestamps persistidos pelo servidor, evitando distorção por polling ou replay SSE.

## Limitações desta execução

- Esta linha de base valida o contrato do avaliador; não representa qualidade de um modelo real.
- Duas falhas intencionais permanecem visíveis para demonstrar que o harness penaliza respostas e campos incorretos.
- 1 de 18 evento está ausente na medição de latência.

O provedor `deterministic-contract-fixture` é uma linha de base de contrato com falhas intencionais; demonstra que o avaliador penaliza erros, mas **não** representa desempenho de GPT, Llama, Mistral, Groq ou Ollama. Uma execução real deve ser registrada separadamente e manter os casos falhos.

## Como reproduzir

```bash
make install
make eval-test
make eval-fake
```

Para uma execução real, baixe os três PDFs oficiais para um diretório usando os nomes de `datasets/manifest.json`, inicie a API com um provedor configurado e rode:

```bash
make eval-live EVAL_API_BASE_URL=http://localhost:8000 EVAL_DOCUMENTS_DIR=/caminho/para/pdfs EVAL_PROVIDER=groq:llama-3.3-70b-versatile
```

O comando ao vivo salva as previsões brutas. Preencha `rubric_score`, `claims_total` e `claims_unsupported` após revisão humana e execute o subcomando `score` para publicar o resultado final.
