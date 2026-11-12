# Demonstração — GovCheck AI

> **Status:** a gravação com um edital real será adicionada após a revisão dos
> resultados. Até lá, as informações abaixo explicam como reproduzir o produto
> sem confundir dados de demonstração com resultados de IA real.

## Vídeo de apresentação

**Vídeo completo:** *em preparação*. Este é o único link que precisa ser
atualizado aqui depois de gravar e publicar o MP4 em um local acessível aos
recrutadores.

<!-- Substituir a linha acima por:
**[▶ Assistir demonstração (aprox. 90 s)](COLE_AQUI_O_LINK_PUBLICADO)**
Não adicionar um arquivo MP4 pesado ao histórico Git.
-->

## O que o vídeo deve demonstrar

| Cena | O que mostrar | Por que importa |
| --- | --- | --- |
| 1. Problema | Tela inicial, proposta de valor e contexto de editais | Produto com caso de uso real |
| 2. Entrada | Upload de **PDF público com texto selecionável** | Processamento de documentos |
| 3. Pipeline | Leitura, indexação, extração, validação externa (se aplicável), crítica e síntese | Orquestração em LangGraph |
| 4. Evidência | Achado com página citada + conferência no PDF aberto ao lado | RAG e rastreabilidade |
| 5. Conversa | Pergunta respondida com citações e, se validado, uma pergunta sem suporte | Chat contextual e limites do modelo |
| 6. Saída | Download Markdown/JSON + diagrama de arquitetura | Integração ponta a ponta |

**Duração recomendada:** entre 75 e 110 segundos. Gravar em 1080p,
preferencialmente em 16:9. Pode acelerar trechos de espera, mas mantenha a
ordem real dos eventos e não oculte falhas relevantes.

## Checklist antes de compartilhar

- [ ] A análise usa `LLM_PROVIDER=groq` ou `ollama`, **não** `fake`.
- [ ] O arquivo é um documento público, sem dados pessoais/confidenciais.
- [ ] Pelo menos um achado foi conferido manualmente na página indicada.
- [ ] O comportamento do chat foi observado em um documento real.
- [ ] A gravação não mostra a chave de API, `.env`, tokens ou credenciais.
- [ ] Nenhuma cena de dados fictícios é apresentada como saída real do LLM.
- [ ] A descrição informa o modelo usado, data e limitações da demonstração.
- [ ] O link abre sem autenticação, depois que o repositório for tornado público.

## Como adicionar o vídeo amanhã

1. Grave o sistema real; exporte `govcheck-ai-demo.mp4` (H.264, 1080p).
2. Publique o MP4 em um local acessível ao público, por exemplo anexando a
   mídia a uma descrição/comentário do GitHub, ou disponibilizando um vídeo
   não listado com link compartilhável.
3. Copie a URL final e substitua a linha **Vídeo completo: em preparação**
   neste arquivo pelo link de reprodução.
4. No README, a seção **Demonstração** já aponta para esta página; o revisor
   encontrará o vídeo sem precisar procurar em Issues ou Actions.
5. Se desejar uma prévia diretamente no README, adicione depois um GIF curto
   e otimizado, gravado do mesmo fluxo real; isso é opcional.

> Em repositórios privados, o acesso ao vídeo e ao próprio código pode exigir
> autorização. Não presuma que o link do GitHub estará disponível ao recrutador.

## Como reproduzir localmente

Siga o [guia Linux](execucao-linux.md) ou o [passo a passo para avaliadores](reviewer-demo.md).
Com os serviços iniciados, acesse `http://localhost:3000`. O botão
**Usar edital de exemplo** demonstra apenas a interface com dados fictícios.

As métricas publicadas em [Avaliação](evaluation.md) são de uma **fixture
determinística**, não de um benchmark validado com LLM real. A comparação com
documentos oficiais continua sendo uma etapa independente.
