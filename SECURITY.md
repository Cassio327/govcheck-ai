# Segurança e uso responsável

O GovCheck AI é um **protótipo de portfólio** para leitura preliminar
de documentos públicos. Não é um parecer jurídico, não verifica
conformidade legal completa e **não foi endurecido para processamento de
arquivos sensíveis ou uso público multiusuário**.

## Limites atuais

- A API usa IDs de sessão anônimos; **não oferece autenticação forte**.
- A retenção automática depende da execução periódica do job de limpeza.
- A limitação de requisições é local à instância.
- Em modo Groq, trechos recuperados do PDF podem ser enviados ao provedor
  remoto conforme seus termos; não carregue documentos confidenciais.
- A recuperação e a crítica de evidências reduzem algumas respostas sem
  suporte, mas não impedem todas as alucinações ou conclusões incorretas.
- PDFs são entradas não confiáveis: execute o protótipo em ambiente isolado,
  não diretamente exposto à internet.

Leia [Modelo de ameaça](docs/threat-model.md) e
[Decisões de engenharia](docs/decisoes-de-engenharia.md).

## Segredos

Nunca comite `.env`, chaves da Groq, tokens GitHub, arquivos de
configuração particulares ou capturas exibindo segredos. Se uma chave for
exposta, **revogue-a e substitua-a**; removê-la de uma página não garante
que terceiros não a tenham visto.

## Relato responsável de vulnerabilidades

Não publique provas de conceito com credenciais ou informações sensíveis
em Issues. Prefira **Private vulnerability reporting** no GitHub caso
esteja habilitado para o repositório; caso contrário, entre em contato com
o responsável pelo projeto por um canal privado antes da divulgação.

## Antes de disponibilizar publicamente

- [ ] Revisar histórico Git e anexos por segredos, inclusive screenshots.
- [ ] Validar o deploy em ambiente isolado e não expor portas ou serviços
      sem autenticação em redes públicas.
- [ ] Garantir que as demonstrações usem exclusivamente documentos públicos.
- [ ] Verificar as condições de uso dos provedores externos.
- [ ] Não apresentar o sistema como certificador jurídico.
