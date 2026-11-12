<div align="center">

# GovCheck AI

### Análise de editais públicos com IA e evidências rastreáveis

**Evidence-first AI for Brazilian public procurement documents.**

`FastAPI` · `LangGraph` · `RAG híbrido` · `Groq / Ollama` · `Next.js` · `PostgreSQL + pgvector`

[**▶ Demonstração**](docs/demo.md) · [**Arquitetura**](docs/architecture.md) · [**Decisões técnicas**](docs/decisoes-de-engenharia.md) · [**Executar no Linux**](docs/execucao-linux.md)

[![CI](https://github.com/Cassio327/govcheck-ai/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Cassio327/govcheck-ai/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Next.js-183153?logo=typescript&logoColor=white)
![Status](https://img.shields.io/badge/status-portfolio%20MVP-205D4B)

</div>

---

> **Por que este projeto existe?** Editais e avisos de contratação concentram datas, exigências de habilitação, critérios de julgamento e obrigações em documentos extensos. Um resumo sem fontes pode ocultar cláusulas ou induzir a erros. O GovCheck AI foi construído para **encontrar informações, organizar achados e mostrar de onde cada afirmação veio**, sem substituir a revisão humana.

## 🎬 Demonstração

**[Ver a página de demonstração e roteiro](docs/demo.md)** — o espaço para o vídeo real já está preparado. A gravação será publicada depois da revisão dos resultados com um PDF oficial.

| Fluxo | O que observar |
| --- | --- |
| **Upload** | PDF textual com leitura e indexação por página (até 5 MiB e 50 páginas) |
| **Análise estruturada** | Prazos, documentos, valores, critérios, sanções e obrigações |
| **Evidências** | Trechos recuperados, número da página e indicação de suporte ou conflito |
| **Chat com RAG** | Perguntas sobre o documento, respostas com citações ou insuficiência de evidências |
| **Relatório** | Exportação Markdown/JSON com achados e proveniência das validações |

> O botão **“Usar edital de exemplo”** carrega dados *fictícios para demonstrar a interface*. Não é uma execução de um LLM. Para observar a análise real, configure Groq ou Ollama e envie um PDF público.

## 🧠 Como funciona

```mermaid
flowchart LR
  U["Revisor<br/>Next.js"] --> API["API + eventos SSE<br/>FastAPI"]
  API --> P["PDF textual<br/>PyMuPDF"]
  P --> DB[("PostgreSQL<br/>pgvector")]
  DB --> R["RAG híbrido<br/>BM25 + embeddings E5"]
  R --> EX["Extração tipada<br/>LangGraph"]
  EX --> V["Validação opcional<br/>PNCP"]
  V --> C["Crítica de evidências"]
  C --> S["Síntese e relatório"]
  S --> API
  EX -.-> L["LLM<br/>Groq / Ollama"]
  C -.-> L
```

**1. Indexação e recuperação.** O PDF é separado em páginas e chunks. A busca combina BM25 e similaridade semântica via RRF. A análise faz seis consultas focadas em categorias, deduplica resultados e limita o contexto a 20 trechos por documento.

**2. Workflow especializado.** Os nós do LangGraph executam extração, validação externa quando aplicável, crítica de evidências e síntese. Os dados gerados pelo LLM passam por contratos Pydantic com limites explícitos.

**3. Rastreabilidade.** Cada achado relaciona a interpretação a fontes do PDF e recebe um estado: `supported`, `unsupported` ou `conflicting`. A verificação no PNCP usa URLs e campos permitidos, sem aceitar destinos arbitrários fornecidos pelo modelo.

**4. Conversação e exportação.** O chat recupera fontes do documento selecionado e exige citações válidas; o usuário pode exportar os resultados e conferir o original.

**Decisões e tradeoffs:** [por que RAG, como o crítico funciona e quais são os limites atuais](docs/decisoes-de-engenharia.md).

## 🚀 Executar localmente

Requisitos: **Git + Docker Engine + Docker Compose v2**. A versão recomendada é Linux (Ubuntu), mas os serviços são containerizados.

```bash
git clone https://github.com/Cassio327/govcheck-ai.git
cd govcheck-ai
cp .env.example .env
nano .env
docker compose up --build -d
docker compose ps
```

Configure no arquivo `.env` antes do primeiro teste com IA real:

```dotenv
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=SUA_CHAVE_PRIVADA
EMBEDDING_PROVIDER=sentence-transformer
INSTALL_EMBEDDINGS=true
```

A chave é obtida no [GroqCloud](https://console.groq.com/keys) e **não deve ser enviada ao GitHub**. O primeiro build com embeddings reais instala dependências maiores; o modelo pode baixar pesos na primeira utilização. Alternativamente, há um adaptador Ollama para execução local.

| Serviço | Endereço |
| --- | --- |
| Interface | http://localhost:3000 |
| Documentação interativa da API | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/health |
| Prontidão do banco | http://localhost:8000/ready |

Para encerrar sem apagar os dados: `docker compose down` (não use `-v` sem intenção de remover volumes).

**Guias:** [Linux passo a passo](docs/execucao-linux.md) · [Windows](docs/validacao-llm-real.md) · [Demonstração para revisão](docs/reviewer-demo.md).

## ✅ Qualidade e avaliação

O repositório inclui testes da API e domínio, migrações reais em PostgreSQL, testes de componentes e Playwright, análise de acessibilidade, auditoria de dependências, Gitleaks, avaliação determinística e build das imagens Docker.

[**Acompanhar o GitHub Actions**](https://github.com/Cassio327/govcheck-ai/actions/workflows/ci.yml)

A avaliação versionada possui **três documentos de referência, 15 perguntas e 15 campos anotados**. A fixture reproduzível verifica o funcionamento das métricas, mas seus números **não são acurácia de um modelo real**. Resultados de Groq/Ollama precisam ser coletados e revisados separadamente.

[Metodologia e resultados de teste](docs/evaluation.md) · [Modelo de ameaça](docs/threat-model.md) · [Contribuição](CONTRIBUTING.md) · [Segurança](SECURITY.md)

## 📂 Organização do código

```text
apps/
  api/                 FastAPI, domínio, RAG, nós LangGraph, adapters e testes
  web/                 Next.js, componentes, fluxo de revisão e testes E2E
packages/
  evaluation/          Dataset versionado, métricas e runner ao vivo
docs/
  demo.md              Entrada para o vídeo e demonstração
  architecture.md      Fluxo, integração PNCP e limites técnicos
  decisoes-de-engenharia.md  Decisões e tradeoffs de implementação
  evaluation.md        Métricas e metodologia
  threat-model.md      Riscos e fronteiras de segurança
  execucao-linux.md    Instalação e execução em Ubuntu/Linux
compose.yaml           Orquestração local e migrações do banco
.github/workflows/ci.yml  Integração contínua e verificações de segurança
```

## ⚠️ Limites e próximos passos

**GovCheck AI é um MVP para análise preliminar, não um parecer jurídico e não um serviço de produção.**

- Requer PDFs com texto selecionável; não há OCR integrado.
- Sessões são anônimas e não substituem autenticação/controle de acesso de produção.
- A busca usa vetores persistidos em pgvector, mas o ranking atual ocorre em memória, sem índice ANN de busca.
- A retenção, as filas e os limites de requisição precisariam ser endurecidos antes de um deploy público.
- Os resultados exigem comparação manual com o documento original; a validação de qualidade com LLM real é uma etapa separada.

**Próximos objetivos:** medir recuperação e factualidade com editais reais, adicionar OCR opcional, autenticação, workers persistentes e observabilidade.

---

<div align="center">

**Do documento à evidência — com revisão humana no controle.**

[Documentação](docs/architecture.md) · [Demo](docs/demo.md) · [Testes](https://github.com/Cassio327/govcheck-ai/actions/workflows/ci.yml)

</div>
