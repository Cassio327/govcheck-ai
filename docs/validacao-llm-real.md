# Primeiro teste com um LLM real (Windows / PowerShell)

Este guia mostra como sair do modo determinístico `fake` e realizar uma
análise verificável. Ele **não** substitui a avaliação de precisão.

## 1. Preparação

Instale Git e Docker Desktop, inicialize o Docker e tenha acesso à internet.
Na sua conta pessoal GroqCloud, crie uma chave em
https://console.groq.com/keys . **Nunca envie a chave ao chat ou ao GitHub.**

No PowerShell:

```powershell
git clone -b feature/govcheck-mvp https://github.com/Cassio327/govcheck-ai.git
cd govcheck-ai
Copy-Item .env.example .env
notepad .env
```

No arquivo `.env`, altere somente as variáveis necessárias:

```dotenv
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=COLE_SUA_CHAVE_APENAS_NO_ARQUIVO_LOCAL
EMBEDDING_PROVIDER=sentence-transformer
INSTALL_EMBEDDINGS=true
```

A chave fica apenas no arquivo local ignorado pelo Git. Verifique o modelo
permitido e os limites de sua conta em
https://console.groq.com/docs/models .

## 2. Inicie a aplicação

```powershell
docker compose up --build -d
docker compose ps
```

O primeiro build com sentence-transformers instala dependências maiores.
O primeiro embedding pode baixar pesos do modelo
`intfloat/multilingual-e5-small`. Se houver pouco espaço ou memória, primeiro
valide o fluxo LLM com `EMBEDDING_PROVIDER=fake` e
`INSTALL_EMBEDDINGS=false`; **essa configuração não mede a qualidade da
busca semântica real**.

Verifique:

- `http://localhost:8000/health` deve responder `{"status":"ok"}`;
- `http://localhost:8000/ready` deve indicar banco disponível;
- `http://localhost:3000` deve carregar o painel.

Se algo falhar:

```powershell
docker compose logs --tail=120 api
docker compose logs --tail=120 migrate
docker compose logs --tail=120 web
```

O `GROQ_MODEL` antigo `llama-3.3-70b-versatile` foi descontinuado para
Free/Developer em agosto de 2026. Esta branch usa
`openai/gpt-oss-120b` como padrão; nenhuma conta ou limite é garantido.

## 3. Faça uma análise real, não o exemplo da interface

Baixe um **edital oficialmente publicado**, com texto selecionável,
até **5 MiB** e **50 páginas**. Não utilize informações privadas.

No painel, envie o PDF (não escolha `Usar edital de exemplo`).
Acompanhe extração, verificação externa (quando houver identificador PNCP),
crítica de evidência e síntese.

Confira pelo menos:

1. Um prazo ou data, confrontando o valor com a página citada no PDF.
2. Um documento exigido ou critério de julgamento, com página citada.
3. Um requisito ausente: faça uma pergunta que o PDF não responda,
   para observar se o chat admite insuficiência de evidência.
4. O relatório Markdown e JSON: os estados
   `supported`, `unsupported` e `conflicting` não são conclusões jurídicas.

Registre em uma tabela os erros, citações inexistentes ou incompletas,
respostas sem suporte, tempo e modelo usado. **Não maquie falhas.**

## 4. Avalie três documentos versionados (opcional, mais convincente)

O avaliador possui três documentos e quinze perguntas rotuladas em
`packages/evaluation/datasets/manifest.json`. Baixe os PDFs das URLs
oficiais nos arquivos `datasets/sources/*.json`, respeitando os nomes
de `local_filename`. Os arquivos devem coincidir com o SHA-256 do manifesto.
Não modifique o hash para contornar divergências: documente a troca de
versão e atualize os rótulos quando necessário.

O runner também exige que cada PDF respeite os limites de upload da API.
Se um edital for maior que o limite, registre essa limitação e não divulgue
um benchmark incompleto como se tivesse usado os três documentos.

Em ambiente com Python 3.12, instale o avaliador e execute os comandos
da raiz do repositório:

```powershell
py -3.12 -m pip install -e "packages/evaluation[dev]"
py -3.12 -m govcheck_eval.runner live --dataset-dir packages/evaluation/datasets --api-base-url http://localhost:8000 --documents-dir "C:\caminho\para\editais" --provider "groq:openai/gpt-oss-120b" --predictions-output packages/evaluation/results/live-predictions.json --output packages/evaluation/results/live-result.json --markdown-output docs/evaluation-live.md
```

Depois, revise manualmente as previsões e preencha os campos de rubrica
pendentes antes de publicar quaisquer métricas de qualidade. O runner
não avalia sozinho se uma afirmação jurídica é verdadeira.

## 5. Critérios para apresentar como portfólio

- Uma análise com LLM real terminou sem erros e com citações auditadas.
- O README informa o provedor, modelo, configuração de embeddings e data.
- A demonstração contém um PDF público e diferencia dados reais de exemplos.
- A CI do pull request está verde.
- O vídeo ou capturas não contêm segredos, nomes privados ou dados sensíveis.
- A publicação do repositório ocorre somente após sua revisão e decisão.

Para encerrar:

```powershell
docker compose down
```

**Não use `docker compose down -v`** a menos que queira apagar os dados locais
do PostgreSQL.
