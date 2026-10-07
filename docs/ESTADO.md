# Estado para continuidade — 07/10/2026

Repositório `/workspace/Davigurumi`, branch `feat/materials-purchasing-reports`. Os PRs #1 e [#2](https://github.com/dvidsales/Davigurumi/pull/2) já foram incorporados à `main`; esta evolução parte de `origin/main` em `9d4ca2e` e reúne rateio manual, relatórios filtrados XLSX e atributos/mínimo de materiais no [PR #3](https://github.com/dvidsales/Davigurumi/pull/3), aberto para revisão. Não fazer reset, apagar `.local/` ou recriar o projeto. Usuário autorizou desenvolvimento autônomo e PR; não autorizou deploy, serviços pagos, merge ou uso de dados reais.

O app evoluiu de contas/materiais/calculadora para os módulos documentados no README. PostgreSQL 17 foi iniciado e validado em Docker. SQLite anterior continua disponível e recebeu migrações compatíveis. Ambos são bancos diferentes.

## Concluído e verificado

- Estoque por camadas e ledger, conversões congeladas, reservas/consumo/liberação, idempotência e teste concorrente em PostgreSQL.
- 106 testes PostgreSQL passaram; SQLite passou 103 com 3 exclusivos de PostgreSQL ignorados.
- Materiais com composição, espessura, agulha recomendada e mínimo opcional; alertas consideram reservas e não se repetem no mesmo dia.
- Compras com rateio manual/proporcional, confirmação congelada e recebimentos com custo por item.
- Relatórios CSV/XLSX de pedidos filtrados por cliente/projeto/produção; caixa permanece global no período.
- Compras/recebimentos, revisões de fichas, alternativas explícitas, snapshots comerciais, PDF e imagens privadas.
- Portal com CSRF e aceite por hash, expiração/revogação, decisões concorrentes, aditivos sem alterar aceite anterior.
- Produção, cronômetro persistido, correções, produção/entregas parciais, pagamentos e reversões manuais.
- Painel, relatórios, reposição, alertas deduplicados, outbox de e-mail, imports/exports e demonstração isolada.
- Pacote completo exportado e restaurado no banco descartável de testes, preservando relações/estoque/pagamentos/PDF/arquivos; links importados revogados.
- Backup PostgreSQL+arquivos restaurado em banco e diretório isolados; hashes de PDFs e arquivos conferidos; corrupção rejeitada.
- Jornada real no Chromium: orçamento 63, sinal 20, consumo 50 g, produção/entrega e quitação por recebimento de 43. Isolamento de duas contas, cache estático, importação, rateio manual, download XLSX e 24 telas de 360 px conferidos.

## Antes de operação pública

Leia PRIVACIDADE, OPERACAO e ROADMAP. Precisamos definir hospedagem Python/HTTPS, chave de produção, SMTP e remetente, destino de backup independente com frequência/retenção e agendador. Falta fechar política legal de retenção/exclusão, implementar eliminação/anonimização compatível com snapshots e tombstones na restauração. Push não está implementado. Não afirmar que todo o PRD ou T01–T26 está aprovado.

## Ferramentas e retomada

Python: `/workspace/.venvs/davigurumi/bin/python`. Container: `davigurumi-postgres`, porta `127.0.0.1:54329`. Segredo local em `.local/postgres.env`: não imprimir nem versionar. Inicie `scripts/dev_postgres.sh`; use `scripts/with_postgres.sh manage.py ...`.

Bancos `davigurumi_browser_features_20261007`, `davigurumi_browser_20261007` e `davigurumi_restore_full_20261007` têm somente exemplos de verificação, separados da base de desenvolvimento. Arquivos de teste: `.local/browser_features_files` e `.local/browser_files`; arquivos restaurados: `.local/restored_files/davigurumi_restore_full_20261007`. Backups de teste ficam fora do checkout em `/workspace/.backups/`. Não selecionar essas bases como dados de usuário.

Servidor/processos não são garantidos após restauração do ambiente. Inicie novamente e confira `/conta/entrar/`. Configuração de onboarding precisa ser salva/publicada pelo usuário para ativar alterações do rascunho. O conteúdo da nova branch precisa estar presente no checkout: `main` já contém os módulos do PR #2; as melhorias desta continuidade exigem incorporar o próximo PR ou selecionar sua branch.

GitHub: API disponível; o PR #1 aparece como incorporado. O envio Git inicial da nova branch retornou erro interno e o mesmo commit/tree foi publicado via API; atualizações Git posteriores funcionaram. PR #2 incorporado; PR #3 aberto nesta branch; evidências atualizadas em VALIDACAO. Não imprimir tokens nem pedir credenciais pelo chat.
