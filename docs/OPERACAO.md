# Operação de desenvolvimento

## Instalar e iniciar

Checkout cloud: `/workspace/Davigurumi`; venv: `/workspace/.venvs/davigurumi`. `requirements.txt` fixa dependências. Não executar `makemigrations` para um simples setup; use migrations versionadas. Não trocar branch/resetar alterações para reinstalar dependências.

```bash
bash scripts/dev_postgres.sh
bash scripts/with_postgres.sh manage.py migrate --noinput
bash scripts/with_postgres.sh manage.py check
bash scripts/with_postgres.sh manage.py reconcile_stock
bash scripts/with_postgres.sh manage.py runserver 127.0.0.1:8000
```

O container usa PostgreSQL 17 e volume `.local/postgres`. Porta exposta apenas em `127.0.0.1:54329`. Helpers usam senha local ignorada e não imprimem valores. TLS é desabilitado exclusivamente nessa conexão loopback; conexões externas usam `POSTGRES_SSLMODE=require` por padrão. Reinicie o servidor após restaurar o ambiente e confirme HTML de login por requisição local. `runserver` é só desenvolvimento.

Sem `POSTGRES_DB`, o Django seleciona `.local/db.sqlite3`. Não apague o arquivo para resolver erro. Os dois bancos não compartilham registros. Não aplicar migrações na produção sem analisar compatibilidade e cópia restaurável.

## E-mail e tarefas

Variáveis documentadas em `.env.example`. O aplicativo lê variáveis do processo, não `.env` automaticamente. Console é padrão somente no desenvolvimento. Produção usa backend sem envio até configurar um backend real; console é rejeitado para não colocar links de recuperação nos logs. Envio real requer backend SMTP, host/porta/remetente/credenciais e verificação do provedor. Não colocar segredos no código, terminal compartilhado ou chat.

```bash
bash scripts/with_postgres.sh manage.py generate_alerts
bash scripts/with_postgres.sh manage.py deliver_notifications
```

O primeiro gera alertas internos de estoque abaixo do mínimo configurado, reposição para pedidos, prazo de produção em até dois dias e parcelas em até três dias, com deduplicação por dia/evento. Não percorre contas demo. O segundo processa até 50 mensagens pendentes e registra retentativas em falha. Nenhum comando instala agendador. É necessário executar periodicamente em produção; ainda não há cron/worker contínuo. Opt-in por e-mail é desabilitado por padrão.

## Backup e restauração isolada

Pausar alterações/entradas de arquivo durante a cópia; pg_dump e ZIP de arquivos não são um snapshot distribuído único. Os scripts abaixo são helpers do container local, não solução de backup externo.

```bash
bash scripts/backup_postgres.sh /workspace/.backups/copia-nova
bash scripts/restore_postgres.sh /workspace/.backups/copia-nova davigurumi_restore_conferencia
DAVIGURUMI_TEST_DB=davigurumi_restore_conferencia \
  DJANGO_MEDIA_ROOT=/workspace/Davigurumi/.local/restored_files/davigurumi_restore_conferencia \
  bash scripts/with_postgres.sh manage.py reconcile_stock
```

Backup cria destino novo, `database.dump`, `files.zip` e manifesto SHA-256, com umask restritiva. Respeita `DJANGO_MEDIA_ROOT` e, para base sintética explicitamente escolhida, `DAVIGURUMI_TEST_DB`. Restaurador exige nome `davigurumi_restore_...`, valida hashes/caminhos antes da criação, usa banco novo e diretório de arquivos novo. Não substitui banco original. Hash verifica integridade contra manifesto confiável; não autentica manifesto adulterado por atacante.

Após restauração, conferir contagens/relações, ledger × camadas/reservas, pagamentos/reembolsos, PDFs e hashes dos objetos privados. Não recolocar base em serviço sem procedimento de exclusões/tombstones quando esses controles estiverem implementados. Export/import de conta revoga links; **backup operacional preserva tokens/sessões existentes** e exigirá decisão operacional de revogação antes da retomada.

Ainda falta: cópia diária agendada, destino independente da máquina, monitoramento de falha, retenção/expurgo, criptografia adequada do destino e simulação regular de recuperação. Backup local sozinho não atende essa exigência.

## Produção futura

Definir host HTTPS, servidor WSGI/ASGI, proxy confiável, segredo diferente do desenvolvimento, `DJANGO_DEBUG=0`, hosts/CSRF origens explícitos, staticfiles, armazenamento privado, SMTP e agendador. Não expor `.local/` ou caminhos de arquivos como mídia pública. Configurar também redação de tokens nos logs do proxy. Cookies seguros/redirect HTTPS existem, mas proxy e HSTS precisam de configuração conforme a infraestrutura.

`python manage.py check --deploy` deve ser revisado nessa configuração real; não foi usado para afirmar prontidão pública. Implantação/merge/serviços pagos ainda não foram executados nem autorizados.


## Controles de segurança e manutenção

Settings sem DEBUG explícito assumem produção e exigem segredo/hosts; `manage.py` opta pelo desenvolvimento local por padrão. Para qualquer comando de operação real, fornecer `DJANGO_DEBUG=0` e demais variáveis explicitamente. Cadastro público de produção fica fechado; `DJANGO_PUBLIC_SIGNUP=1` só deve ser considerado após verificação de e-mail/controle de abuso.

Limites técnicos atuais: uploads privados 5 MB, pacote 50 MB, corpo não-arquivo 1 MB, até 500 campos/10 arquivos, 20 prévias/recibos recentes por conta, exportação de relatórios até 5000 linhas, 15 tentativas de autenticação/900 s, 120 leituras de portal/60 s, 60 leituras de painel/relatórios/60 s e 120 outras gravações/60 s por endereço direto. Não substituem quotas de armazenamento nem proteção de borda. Arquivos têm permissão 0600 e diretórios privados 0700.

```bash
bash scripts/with_postgres.sh manage.py prune_transient
# Após conferir a simulação, aplicar quando autorizado:
bash scripts/with_postgres.sh manage.py prune_transient --apply
```

A limpeza remove somente limites expirados há mais de um dia, sessões expiradas e prévias/recibos com mais de 30 dias. Não elimina estoque, contratos, pagamentos, arquivos ou auditoria. A UI permite descartar apenas prévias não aplicadas. Não foi executada limpeza dos dados de desenvolvimento nesta continuidade.

Conta suspensa não faz login nem acessa portal; dados e hashes históricos continuam armazenados. Reativação deve ser feita administrativamente com registro/motivo e não reativa links revogados. Isso não é procedimento de eliminação de dados.
