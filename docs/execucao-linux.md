# Executar o GovCheck AI no Linux

Este guia usa o código já enviado à branch `feature/govcheck-mvp`. A `main`
ainda não contém o MVP. **Não é necessário fazer merge** para executar o projeto.

## 1. Verificar Git e Docker

Em um terminal Linux, execute:

```bash
git --version
docker --version
docker compose version
docker info
```

O projeto precisa de Git, Docker Engine em execução e o plugin Compose v2
(`docker compose`, com espaço, não `docker-compose`). Se ainda não possui
Docker, siga o guia oficial da sua distribuição:
https://docs.docker.com/engine/install/

Ubuntu: https://docs.docker.com/engine/install/ubuntu/

Debian: https://docs.docker.com/engine/install/debian/

Se o serviço estiver instalado, mas parado, e você usa Docker Engine:

```bash
sudo systemctl enable --now docker
```

Se `docker info` falhar por permissões, você pode executar os comandos
`docker compose` seguintes com `sudo`. Também é possível configurar o
acesso sem `sudo` seguindo
https://docs.docker.com/engine/install/linux-postinstall/ .
**A associação ao grupo docker concede privilégios equivalentes a root.**

## 2. Baixar a branch correta

```bash
git clone --branch feature/govcheck-mvp --single-branch https://github.com/Cassio327/govcheck-ai.git
cd govcheck-ai
ls -la
```

Você deve encontrar `README.md`, `compose.yaml`, `apps/` e `docs/`.
Se receber "Repository not found" ou erro de autenticação, o repositório
ainda é **privado**: autentique sua conta GitHub antes de clonar. Uma opção
é instalar o GitHub CLI, executar `gh auth login`, escolher GitHub.com
e HTTPS, e então repetir o clone. **Nunca envie tokens ao chat.**

Caso já tenha o clone:

```bash
git fetch origin
git switch feature/govcheck-mvp || git switch -c feature/govcheck-mvp --track origin/feature/govcheck-mvp
git pull --ff-only origin feature/govcheck-mvp
```

## 3. Configurar a IA real

Crie uma chave em https://console.groq.com/keys e verifique os modelos
disponíveis à sua conta em https://console.groq.com/docs/models .
Mantenha a chave somente no seu computador.

```bash
cp .env.example .env
nano .env
```

Altere estas variáveis do arquivo `.env`:

```dotenv
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=SUBSTITUA_PELA_CHAVE_LOCAL
EMBEDDING_PROVIDER=sentence-transformer
INSTALL_EMBEDDINGS=true
```

**Não compartilhe nem comite `.env`.** O `.gitignore` o exclui do controle
de versão. O modelo de embeddings será baixado no primeiro uso, com
necessidade de memória, disco e conexão à internet.

## 4. Inicializar o projeto

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Se não possuir acesso ao daemon do Docker sem `sudo`, use
`sudo docker compose` de forma consistente. Os serviços são PostgreSQL,
migrações Alembic, API FastAPI e frontend Next.js.

Abra:

- Interface: http://localhost:3000
- OpenAPI: http://localhost:8000/docs
- Saúde: http://localhost:8000/health
- Prontidão do banco: http://localhost:8000/ready

Para inspecionar erros sem expor sua chave, evite compartilhar logs completos
antes de remover valores privados:

```bash
docker compose logs --tail=80 api
docker compose logs --tail=80 migrate
docker compose logs --tail=80 web
```

## 5. Confirmar que não está no modo de demonstração

Envie pela interface **um edital público com texto selecionável**, menor
ou igual a 5 MiB e com no máximo 50 páginas. Não use o botão "Usar edital
de exemplo" para comprovar o funcionamento da IA; ele carrega dados
fictícios da interface.

Verifique um prazo, um requisito de habilitação e uma resposta do chat
contra as páginas reais do PDF. Experimente também uma pergunta sem resposta
no documento. Exporte o relatório e registre citações incorretas, erros e
tempo de resposta. A CI testa contratos e fixtures; ela **não mede**
automaticamente a qualidade do modelo real.

## 6. Encerrar

```bash
docker compose down
```

Não use `docker compose down -v` sem querer apagar o volume do banco.

Para o roteiro de apresentação aos recrutadores, consulte
[reviewer-demo.md](reviewer-demo.md).
