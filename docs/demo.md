# Demonstração técnica — GovCheck AI

> **Status da publicação:** a edição final do vídeo está concluída e revisada, mas **o MP4 ainda não foi anexado ao GitHub**. O [local de publicação é a issue #3](https://github.com/Cassio327/govcheck-ai/issues/3); a issue não é, por enquanto, um link de reprodução.

## Sobre o vídeo final

| Propriedade | Valor |
| --- | --- |
| Gravação original | 12/11/2026; execução com documento público e LLM real |
| Edição selecionada | `govcheck-ai-demo-revisado.mp4` |
| Duração | **2min13s** (133 segundos) |
| Formato | MP4, H.264, 1920 × 1080, 15 FPS, sem áudio |
| Tamanho | Aproximadamente **5,2 MB** |
| Acessibilidade | **22 legendas em português incorporadas ao vídeo**; [arquivo SRT editável](demo-captions.srt) |

A demonstração utiliza o **Aviso de Contratação Direta nº 90007/2025**. A gravação original possui aproximadamente três minutos; a edição removeu trechos de espera e digitação repetitiva, preservando a seleção do arquivo, o processamento, a consulta aos achados, perguntas, a resposta de evidência insuficiente e as duas exportações.

## Sequência exibida

| Tempo do vídeo final (aproximado) | Cena | O que a cena evidencia |
| --- | --- | --- |
| 0:00–0:29 | Seleção e envio do PDF, processamento e seis achados estruturados | Fluxo de entrada e apresentação de achados para revisão |
| 0:29–1:00 | Perguntas sobre o objeto e o valor estimado | Chat com trechos e páginas do documento |
| 1:00–1:26 | Pergunta sobre participação | Recuperação de condições e referências verificáveis |
| 1:26–1:45 | Pergunta sobre o percentual exato da multa | Abstenção quando a evidência é insuficiente |
| 1:45–2:13 | Relatório Markdown e exportação JSON | Achados estruturados, citações, páginas e estados de evidência |

### Como interpretar a demonstração

- **Execução real, não fixture de interface:** o fluxo mostrado foi capturado com PDF público e provedor LLM configurado. O botão **“Usar edital de exemplo”**, por outro lado, usa dados fictícios e não corresponde a essa execução.
- **Arquitetura versus evidência visual:** as legendas mencionam **RAG híbrido e LangGraph** porque essas tecnologias fazem parte da implementação documentada. O vídeo da interface, isoladamente, não comprova o algoritmo interno; consulte [arquitetura](architecture.md) e [código](../apps/api/src/govcheck/application/analysis/graph.py).
- **Rastreabilidade não equivale a veracidade jurídica:** trechos e páginas são exibidos, mas a edição não mostra uma validação completa lado a lado do PDF original para cada achado. A revisão humana é necessária.
- **Validação externa:** a existência de um nó/ferramenta PNCP não significa que uma chamada externa tenha necessariamente acontecido na gravação.
- **Sem alegações de acurácia:** o vídeo é uma demonstração funcional pontual, não um benchmark de LLM real. A avaliação determinística versionada em [evaluation.md](evaluation.md) usa fixtures e não mede a acurácia de Groq/Ollama.

## Publicar o MP4 no GitHub

1. **Baixe e confira** a versão revisada `govcheck-ai-demo-revisado.mp4` (5,2 MB). Verifique que nenhuma chave, token, dado pessoal ou informação confidencial aparece na gravação.
2. Abra a [issue pública de demonstração #3](https://github.com/Cassio327/govcheck-ai/issues/3).
3. Na caixa de comentário, **arraste o arquivo MP4** ou use o seletor de anexos. Aguarde o GitHub concluir o upload.
4. Publique o comentário para tornar a URL da mídia acessível. Abra o link em janela anônima para confirmar a reprodução.
5. Copie o **link real do MP4** gerado pelo GitHub. Esse link será colocado nesta página e na seção [Demonstração do README principal](../README.md#-demonstração).

> **Pendente:** o link direto para reprodução só será inserido após o anexo existir. Não há vídeo hospedado ou endpoint de inferência público por trás dos links atuais.

## Para executar e verificar por conta própria

- [Guia para avaliadores](reviewer-demo.md): diferencia dados de exemplo, testes e uso de LLM real.
- [Execução no Linux](execucao-linux.md): ambiente, dependências e configuração local.
- [Arquitetura](architecture.md): pipeline RAG, orquestração e decisões técnicas.
- [Avaliação](evaluation.md): métricas e proveniência, incluindo seus limites.
- [Segurança](../SECURITY.md): cuidados com documentos, credenciais e exposição de serviços.

**Responsabilidade:** o GovCheck AI auxilia a leitura preliminar de documentos de contratação pública. Não é parecer jurídico, não comprova conformidade e não dispensa revisão humana.
