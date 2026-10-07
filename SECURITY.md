# Revisão de segurança — 07/10/2026

Esta aplicação continua em desenvolvimento e **não deve ser aberta ao público nesta etapa**. A revisão cobre o código dos módulos accounts, config, materials, pricing, purchasing, projects, sales, production, finance, operations e portability, as dependências fixadas, os fluxos HTTP de teste e os helpers de backup. Não inclui infraestrutura de um provedor, pentest independente ou dispositivos reais.

## Correções desta revisão

| Área | Proteção acrescentada |
| --- | --- |
| Inicialização | WSGI falha sem chave/hosts de produção. DEBUG é desativado por padrão nas settings; manage.py opta pelo desenvolvimento local. Chave conhecida de desenvolvimento, chave curta e hosts globais são rejeitados em produção. |
| Cadastro | Cadastro público desativado por padrão fora do desenvolvimento; habilitação requer configuração explícita. |
| Senhas e conta | Mínimo de 12 caracteres, recuperação em uma hora, troca de senha, revogação de todos os links e suspensão com senha/consentimento. Contas suspensas não acessam o portal, mesmo se um token ainda não tiver sido revogado. |
| Tentativas e gravação | Limites compartilhados no banco: autenticação/confirmação de senha, leitura do portal, painel/relatórios e demais operações de gravação. Endereço direto é usado; cabeçalhos de encaminhamento não são confiados automaticamente. |
| Uploads | Tamanho total declarado é verificado antes do CSRF/formulário; handler limita cumulativamente os bytes de arquivos recebidos, mesmo sem confiar em upload.size. Limites de campos/arquivos e permissões privadas configurados. |
| Respostas | CSP, Permissions-Policy e no-store alcançam também erros/429/403; conteúdo privado não entra no cache da PWA. |
| Logs e e-mail | Tokens de recuperação e portal são redigidos nos loggers Django. Console de e-mail é proibido em produção. Backend de e-mail não configurado não marca mensagens como enviadas. |
| Portabilidade | Exportação recusa exceder 10000 registros/50 MB, sem truncar história. Arquivos são lidos com limite e verificados por hash/tamanho. Prévias limitadas por conta, descarte apenas antes de aplicação e tratamento de erros de restauração sem sobrescrever dados. |
| Histórico | Compensações, despesas e reversões preservam a origem; PostgreSQL rejeita compensações incompatíveis, alteração/eliminação de despesas e eliminação do ledger físico. Edição de metadados não sobrescreve o estado de arquivamento por uma instância antiga. |
| CI | Auditoria de dependências e análise estática adicionadas aos checks, com permissões de repositório somente para leitura. |

## Evidências

- Suítes PostgreSQL/SQLite e navegador descritas em [VALIDACAO](docs/VALIDACAO.md).
- Matriz de **45 rotas privadas**: outra conta recebe 404 em POST e 404/405 em GET, usando IDs estrangeiros existentes. Arquivos, portal, despesas e recuperação têm testes negativos adicionais.
- Testes de CSRF, redirecionamento externo de login, limites compartilhados, upload em chunks, suspensão, invalidação de sessões e configuração WSGI.
- `pip-audit` não encontrou vulnerabilidades conhecidas nas versões auditadas. Isso depende dos avisos disponíveis na data.
- Bandit não encontrou achados médios/altos. Achados baixos revisados incluem credenciais sintéticas de testes, subprocessos de teste com argumentos fixos e importação da classe ParseError. A classe é usada somente para capturar erro; parsing XLSX usa defusedxml, confirmado ativo.
- Django `check --deploy` foi executado com configuração sintética e chave temporária não publicada: permanecem W005/W021 sobre subdomínios/preload HSTS. Não habilitar esses controles indiscriminadamente antes de conhecer o domínio. Não houve deploy.

## Limites atuais e itens antes de abertura

1. **Retenção e backups:** exclusão integral administrativa, tombstones assinados externos, bloqueio/reaplicação após restauração e expiração de cópias locais implementados nesta continuidade local. Não executados em dados reais. Política/prazos, expurgo em provedores e anonimização seletiva ainda dependem de definição. Ver [EXCLUSAO_RETENCAO](docs/EXCLUSAO_RETENCAO.md).
2. **Infraestrutura:** verificar HTTPS/proxy, identidade do servidor PostgreSQL e TLS, usuário de banco com privilégio mínimo, permissões/criptografia do armazenamento, logs externos e destino de backup independente. A senha local é apenas do container de desenvolvimento.
3. **Contas e abuso:** MFA/verificação de e-mail não estão implementados; cadastro permanece fechado por padrão em produção. Cotas por conta incluem categorias de registros e 50 MB de imagens/PDFs, com lock e proteção na importação. Limites por IP e cotas não substituem controle de abuso distribuído, proteção de borda ou monitoramento. Proxy/IP compartilhado deve ser definido conscientemente.
4. **Autorização:** a aplicação filtra por proprietário; triggers são defesa adicional, não RLS nem autorização para quem possuir credenciais diretas do banco. A assinatura do pacote não criptografa dados e depende da proteção/rotação da chave original.
5. **Portal:** link é uma credencial de posse, não verificação da identidade do cliente. Revogação não recolhe arquivos já baixados. Logs do proxy precisam de redação própria.
6. **Validação adicional:** revisão independente, cargas/cotas, navegadores/dispositivos reais e acessibilidade. Push não foi habilitado/implementado nesta revisão; nova integração exige revisar endpoints e evitar SSRF e conteúdo pessoal em tela bloqueada.

## Repetir checks

```bash
bash scripts/with_postgres.sh manage.py check
bash scripts/with_postgres.sh manage.py makemigrations --check --dry-run
bash scripts/with_postgres.sh manage.py test --noinput
pip-audit -r requirements.txt
bandit -r accounts config materials purchasing projects sales production finance operations portability pricing -ll
```

Ferramentas de auditoria são separadas das dependências da aplicação; a CI instala versões fixadas. Para evidências no navegador, usar exclusivamente base descartável conforme VALIDACAO. Comunicar incidentes diretamente ao responsável pelo repositório por canal privado; não publicar dados reais, pacotes, tokens ou credenciais em issues.

## Continuidade local

Controle de exclusão sem endpoint público: prévia, suspensão prévia, registro externo assinado/fsync, manutenção transacional com locks e guardas reativados, remoção de arquivos após commit e reaplicação. Processo web deve ter somente leitura do registro e um usuário de banco restrito. A manutenção requer permissões próprias; não conceder ALTER TABLE ao runtime por causa do comando. O registro/key nunca podem ser substituídos pela versão de um backup antigo.

Importação recusa origem/destino excluídos; sessões e portal verificam tombstones e falham fechados em produção sem configuração. Envios pendentes respeitam exclusão/suspensão/opt-out; corpo de e-mail não inclui dados internos. Cotas também protegem cópias do demo/importações. Foco de teclado, contraste e tabelas roláveis foram revistos; emulação e auditoria automática não substituem aparelhos/leitor de tela reais.

`check_readiness` é uma prévia local dos requisitos de produção, sem deploy; `--strict` falha quando incompletos. O cloud continua corretamente identificado como desenvolvimento, sem requisitos de produção concluídos. Alterações desta continuidade são locais, sem push/novo PR.
