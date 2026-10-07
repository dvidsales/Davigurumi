# Operação, segurança e recuperação

## Ambiente atual

Desenvolvimento isolado, SQLite e servidor Django. Dados sintéticos usados nos testes.
Não há deploy, worker, provedor de e-mail, arquivos de clientes ou cobrança ativada.
Processos não sobrevivem necessariamente à restauração da máquina: o servidor deve
ser iniciado novamente a partir das instruções salvas do ambiente.

## Antes de produção

1. PostgreSQL com papel não administrativo; testar vínculos/ownership e concorrência.
2. `DJANGO_DEBUG=0`, chave secreta forte no ambiente, hosts reais, TLS, cookies seguros,
   servidor WSGI suportado e estáticos separados. Executar `check --deploy`; o padrão
   local não passa pelos critérios de produção por design.
3. SMTP transacional, verificação de endereço e recuperação entregue de fato.
4. Rate limiting de login/cadastro/reset/portal, quotas, logging sem tokens/senhas e CSP.
5. Backup/restauração independente e rotina monitorada; política de retenção e suporte.
6. Revisão de acessibilidade/segurança e testes da jornada completa antes de dados reais.

Secrets ficam em variáveis/bindings seguros, nunca em `.env.example`, logs, exports ou
scripts. Em produção, não usar sessão/secret de desenvolvimento. `POSTGRES_SSLMODE`
padrão é `require`; validar cadeia com `verify-full` e CA do provedor antes do deploy.

## Backup: planejado, ainda não operacional

SQLite de desenvolvimento pode ser copiado com API `sqlite3.Connection.backup` para
snapshot consistente; não copiar arquivo aberto às cegas. PostgreSQL deverá usar
`pg_dump`/restauração isolada. Banco, arquivos e manifesto de hashes precisam de janela
consistente; secrets têm procedimento separado. Restrinja leitura das cópias, que
contêm hashes de senhas e dados privados.

Proposta do PRD: cópia diária, sete diárias/quatro semanais, RPO 24h, RTO um dia útil.
São metas, **não SLA nem execução comprovada**. Cópia na própria máquina é contingência
local, não destino independente. Falta definir responsável, destino, criptografia,
frequência, credenciais e monitoramento; isso bloqueia piloto real, não desenvolvimento.

Teste de recuperação exigido: restaurar banco/objetos em ambiente vazio, conferir
usuários, saldos, versões, custos e permissões; aplicar tombstones para não ressuscitar
dados pessoais eliminados. Não houve teste de backup/restauração nesta entrega.

## Deploy e retorno

Escolher hospedagem Python e PostgreSQL após validar limites, uso comercial e cobrança.
Usar dados/credenciais distintos entre desenvolvimento e produção. Pipeline futuro:
testes → migrations compatíveis → collectstatic → deploy WSGI → smoke funcional.
Antes de migração real, criar cópia restaurável e ensaiar em staging; rollback de código
não desfaz automaticamente mudanças no banco. Nunca usar snapshot local como prova de
publicação ou continuidade do serviço.

## Privacidade e retenção

Minimizar dados de clientes/evidências; nunca exigir cartão, CNPJ ou endereço sem
finalidade. Retenção precisa mapear categoria/finalidade/prazo/fundamento. Histórico
comercial não autoriza retenção pessoal indefinida. Eliminação deverá alcançar snapshots,
arquivos, caches e logs, com tombstones reaplicados após restore. Termos e política são
pendentes; revisão jurídica não foi feita e não se afirma conformidade LGPD.
