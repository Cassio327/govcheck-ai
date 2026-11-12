# Demonstração — GovCheck AI

> **Status:** gravação realizada em **12 de novembro de 2026** com um PDF
> oficial e LLM real. Versão editada em Full HD (H.264, ~2min05s, sem áudio).
> **Aguardando apenas anexar o arquivo MP4 ao GitHub.**

## Vídeo de apresentação

**[🎬 Área de publicação do vídeo](https://github.com/Cassio327/govcheck-ai/issues/3)**

O arquivo foi editado a partir de uma execução do programa com o
**Aviso de Contratação Direta nº 90007/2025**. A edição remove períodos de
espera e janelas técnicas, acrescentando legendas de seção. Não substitui
resultados reais por fixtures nem altera os valores mostrados pelo sistema.

**O que está no registro:** processamento do PDF, seis achados estruturados
para revisão, perguntas e respostas com trechos citados, reconhecimento de
evidência insuficiente e conferência visual com o documento original.

**Para concluir a publicação:** anexar
`govcheck-ai-demo-final.mp4` à [issue de demonstração](https://github.com/Cassio327/govcheck-ai/issues/3).
Depois substituir o link acima pela URL de vídeo gerada pelo GitHub, para
que o player apareça diretamente nesta página e no README.

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

## Como publicar a gravação

1. Utilize a versão editada `govcheck-ai-demo-final.mp4` (H.264, 1080p; ~2,5 MB).
2. Na [issue #3](https://github.com/Cassio327/govcheck-ai/issues/3), arraste o MP4 para um comentário e publique-o. Alternativamente,
   no terminal autenticado: `gh issue comment 3 --attach ~/Downloads/govcheck-ai-demo-final.mp4`.
3. Copie a URL de mídia do comentário e substitua o link da seção **Vídeo de apresentação** pela URL de reprodução.
4. Atualize a seção **Demonstração** do README para oferecer um acesso imediato ao vídeo.
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
