# Estado para continuidade — 07/10/2026

Repositório `/workspace/Davigurumi`, branch `feat/inline-quote-pieces`, baseada na main após PR #8 incorporado. Cadastro de peças no orçamento e preenchimento automático prontos para revisão, com migração aditiva `projects.0003`. Não apagar `.local/` ou recriar o projeto; não fazer deploy público ou merge sem autorização.

O app evoluiu de contas/materiais/calculadora para os módulos documentados no README. PostgreSQL 17 foi iniciado e validado em Docker. SQLite anterior continua disponível e recebeu migrações compatíveis. Ambos são bancos diferentes.

## Concluído e verificado

- Estoque por camadas e ledger, conversões congeladas, reservas/consumo/liberação, idempotência e teste concorrente em PostgreSQL.
- 145 testes PostgreSQL passaram; SQLite passou 140 com 5 exclusivos de PostgreSQL ignorados.
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

GitHub: PRs #1–#3 incorporados; novo trabalho está na branch de segurança. Não imprimir tokens ou pedir credenciais pelo chat.

Revisão detalhada em [SECURITY.md](../SECURITY.md): isolamento de 45 rotas privadas, limites de uploads/requisições/exportações, suspensão e revogação, senha e configuração de produção restritiva. Novos fluxos incluem despesas reais/reversões, recuperação de estoque, arquivamento, aditivos reconciliados, calendário, comparação de versões, referências de custo e relatórios de movimentos. Ainda faltam push, retenção/anonimização/tombstones, dispositivos reais e avaliação independente.

## Continuidade essencial — envio autorizado

O usuário pediu priorizar pendências essenciais e deixar notificações para o final; posteriormente autorizou enviar a atualização ao GitHub. PR #4 já incorporado em `66a5c66`. A continuidade foi reaplicada sobre essa main na branch `feat/privacy-and-local-testing`, para novo PR. Não fazer merge ou deploy.

Exclusão integral administrativa com prévia, tombstones externos assinados, bloqueio de sessão/portal/importação e reaplicação na restauração; expiração de backups reconhecidos com simulação por padrão. Nenhum `--apply` foi executado em dados reais/backups existentes. Tests usaram apenas bancos de teste e diretórios temporários. Cotas por conta, orçamento de imagens/PDFs, consultas do painel e WCAG/foco/tabelas corrigidos. Leia EXCLUSAO_RETENCAO antes de qualquer uso administrativo.

160 testes PostgreSQL passaram; SQLite 155 passaram/5 exclusivos ignorados. Chromium: 31 telas de 360 px e telas principais em 768/1024, zero violações WCAG automáticas; carga sintética de 48 leituras/4 simultâneas, zero falhas. Auditorias sem vulnerabilidades conhecidas/achados médios ou altos. Nenhuma migração nova nesta continuidade.

Base sintética adicional `davigurumi_browser_essentials_20261007`, arquivos `.local/browser_essentials_files`, servidor local de teste 127.0.0.1:8104 (reiniciar após restauração). Roteiro de homologação em TESTES_DISPOSITIVOS: computador e celular; tablet se fizer parte da rotina. `check_readiness` retorna false neste ambiente de desenvolvimento; não é produção nem autoriza abertura pública.

## Feedback do usuário

Branch `feat/usability-feedback`: navegação ativa incluindo relatórios/demo/segurança; filtros integrados; cadastro de contatos dentro da compra/orçamento com busca/ID/histórico; biblioteca de peças com pedidos relacionados; orçamento em etapas, publicação vazia guiada e confirmações exibidas somente quando pertinentes. 164 testes PG; SQLite 159/5 ignorados; navegador e WCAG automáticos passaram. Não alterar ou apagar bases do usuário para aplicar esta versão.
