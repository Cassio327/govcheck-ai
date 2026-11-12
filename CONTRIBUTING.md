# Contribuindo com o GovCheck AI

O projeto prioriza **código reprodutível, rastreabilidade das respostas e
limites explícitos de confiança**. Mudanças nos prompts, no RAG ou nas
ferramentas precisam vir acompanhadas de testes que mostrem o comportamento
esperado — inclusive casos em que a aplicação deve recusar uma conclusão.

## Ambiente de desenvolvimento

- Python 3.12
- Node.js 24 e pnpm 11.25.0
- Docker Engine/Compose v2 para integração com PostgreSQL/pgvector

```bash
make install
make verify
```

O fluxo completo da CI também executa migrações PostgreSQL, Playwright,
avaliação determinística, auditoria de dependências, scan de segredos e
construção das imagens Docker.

## Regras para alterações

1. Crie uma branch com nome descritivo e abra um pull request.
2. Mantenha dependências organizadas entre `domain`, `application` e
   `infrastructure`. Não mova regras de negócio para rotas HTTP.
3. Inclua testes para alterações em contratos Pydantic, citações, fontes
   externas, isolamento de sessão e tratamento de erros.
4. Ao alterar prompts, documente pelo menos um caso positivo e um
   caso adversarial/sem evidência.
5. Não confunda testes com `LLM_PROVIDER=fake` com avaliação de qualidade
   de LLM real.
6. Use somente editais públicos em exemplos. Nunca adicione `.env`,
   chaves, tokens, PDFs com dados sensíveis ou gravações mostrando credenciais.
7. Atualize README e documentação se modificar o comportamento demonstrável
   pela interface ou o passo a passo de instalação.

## Organização

| Caminho | Responsabilidade |
| --- | --- |
| `apps/api/src/govcheck/domain/` | Contratos e invariantes de domínio |
| `apps/api/src/govcheck/application/` | Casos de uso, orquestração e RAG |
| `apps/api/src/govcheck/infrastructure/` | Persistência, embeddings, LLMs, PDF e PNCP |
| `apps/web/` | Interface e testes Next.js |
| `packages/evaluation/` | Dataset, avaliação e runner |
| `docs/` | Arquitetura, decisões e demonstrações |

## Critérios antes de merge

- [ ] CI aprovada no PR.
- [ ] Documentação e schema HTTP continuam coerentes.
- [ ] Não há informação privada nos commits ou no vídeo.
- [ ] Alterações de IA têm casos de teste e limitações documentadas.
- [ ] Testes com provedores reais, quando realizados, especificam modelo,
      conjunto de PDFs e data, sem substituir a revisão humana.

Este é um **MVP de portfólio**, não um serviço público de produção.
