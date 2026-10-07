# Evidências — 07/10/2026

Validação com dados sintéticos no cloud. Testes automatizados não substituem homologação do usuário, operação do provedor ou avaliação legal. Não declarar T01–T26 completos.

## Suíte Django

PostgreSQL 17 real em container: cadastro/sessão/reset, CSRF/limite de tentativas, isolamento, Decimal, estoque inicial/idempotência, camadas/FIFO/conversões, reservas, compras/parciais/rateio, revisões/alternativas, versões/PDF/imagens, tokens, aceite, aditivos, produção/timer/correções/entregas, financeiro, outbox, relatórios, imports/pacote e demo. Resultado: **145 testes passaram no PostgreSQL**; no SQLite, **140 passaram e 5 específicos de PostgreSQL foram ignorados**, sem falhas.

Concorrência efetiva em PostgreSQL: duas reservas de 80 sobre 100 aceitam somente uma; aprovação e recusa simultâneas produzem somente uma decisão. SQL direto cruzando proprietário ou alterando conteúdo publicado é rejeitado nos testes específicos. SQLite executa os contratos aplicáveis; cinco testes exclusivos de PostgreSQL são explicitamente ignorados.

Exemplos verificados: 3 apresentações de 254 → 762 g com conversão congelada; duas camadas 100 g a 0,10/0,20 com média e consumo FIFO; 508 g → reserva/consumo/cancelamento sem restaurar material usado; pagamento 50+30−10 → líquido 70; sinal alocado ao pedido sem nova entrada; aditivo altera saldo preservando aceite anterior; pacote completo conserva relações/dinheiro/PDF/arquivos e revoga links.

## Navegador

Chromium real via Playwright, servidor ligado à base sintética separada `davigurumi_browser_security_20261007` e arquivos `.local/browser_security_files`:

- Cadastro → material 508 g a 0,10 → ficha 120 g + 1h a R$30 → orçamento R$63.
- Imagem escolhida, publicação, portal com formulário nativo/CSRF e aceite explícito; material interno não aparece no portal.
- Sinal R$20 anterior ao pedido; saldo R$43 após conversão sem duplicar sinal.
- Reserva, início/recarga/pausa do timer, consumo reservado de 50 g, produção, entrega e recebimento final R$43.
- Pedido concluído/entregue/quitado; estoque físico 458, reservas liberadas.
- CSV com prévia/confirmação; outra conta recebe 404 ao acessar material/projeto/orçamento/pedido; entrada/saída do demo não mistura materiais.
- 31 rotas em 360×800 sem overflow horizontal de página; zero erros JavaScript e zero respostas 5xx.
- Compra com item de preço zero e frete R$7: rateio manual confirmado, sem entrada física implícita; tela de rateio também conferida em 360 px.
- Metadados opcionais e mínimo 500 g: aviso visível após consumo; testes verificam reservas reduzindo o disponível e deduplicação por dia/conta.
- XLSX filtrado por projeto/produção baixado no navegador e aberto com openpyxl: uma linha, total 63, recebido 63, saldo 0 e crédito 0. Testes verificam seleção de cliente estrangeiro rejeitada e nomes com aparência de fórmula neutralizados.
- Cache do service worker somente `/static/`; banner offline verificado.

O teste encontrou/corrigiu: formato de campos HTML date, moeda no portal, Origin null por política no-referrer no Chromium HTTP e colisão do campo financeiro `method` com propriedade do formulário no JavaScript. Capturas com dados fictícios: [desktop](images/visao-geral-desktop.png) e [celular](images/visao-geral-mobile.png).

Para repetir, criar **novo banco descartável** e executar migrations nele. Iniciar servidor com `DAVIGURUMI_TEST_DB=<base_descartavel>` e `DJANGO_MEDIA_ROOT=<diretorio_descartavel>` usando `scripts/with_postgres.sh`. Depois:

```bash
DAVIGURUMI_SMOKE_ISOLATED=1 \
DAVIGURUMI_SMOKE_URL=http://127.0.0.1:8101 \
node scripts/smoke_browser.cjs
```

Requer Playwright/Chromium; `NODE_PATH` pode precisar apontar para a instalação do ambiente. O script recusa executar sem declaração de isolamento e deixa seus registros sintéticos para validação de backup. Não o apontar para base pessoal/produção. API de criação de contas possui limite por IP; repetir muitos testes em sequência pode gerar 429 esperado.

## Backup

Backup completo da base sintética em `/workspace/.backups/davigurumi-full-20261007`, restaurado em `davigurumi_restore_full_20261007`. Nove materiais reconciliados sem divergência; pedido 63, dois pagamentos totalizando 63, saldo zero, estoque 458 e imagem por hash conferidos. Todos os PDFs publicados mantiveram o mesmo SHA-256 entre origem/restauração. Cópia com dump adulterado foi rejeitada antes de criar banco.

Primeira prova de fundação também preservou material 508 e hash de senha em banco separado. Nenhuma restauração substituiu a base original. Esses backups continuam na mesma máquina: não comprovam independência, agendamento diário ou retenção.

## Limites das evidências

SMTP testado com backend em memória/falha simulada, sem e-mail externo real. O histórico de CI PostgreSQL do PR #2 passou. PRs #1–#3 incorporados; consulte os checks do novo PR de segurança para execução remota. Não verificados: hospedagem, cobrança/cotas de fornecedor, carga de produção, dispositivos Safari/Android, push, leitor de tela, política legal/exclusão/tombstones e recuperação com perdas reais de infraestrutura.

## Revisão de segurança e novos fluxos

145 testes incluem matriz de isolamento de 45 rotas, limites de arquivos/requisições, configuração WSGI restritiva, cadastro fechado em produção, troca de senha, suspensão/revogação, limpeza de dados transitórios, cotas de prévias, despesas/reversões, compensações de estoque e guardas SQL. Também cobrem aditivos com itens retirados e consumo histórico, calendário, comparação comercial, referências de custo, modelos/importação de metadados e exportação de movimentos.

`pip-audit` não encontrou vulnerabilidades conhecidas nas dependências fixadas. Bandit não encontrou alertas médios ou altos; alertas baixos foram revisados. `check`, verificação de migrações e `pip check` passaram. `check --deploy` com configuração sintética aponta apenas inclusão de subdomínios e preload de HSTS, decisões pendentes do domínio real. Isso não comprova ausência de vulnerabilidades; veja [SECURITY.md](../SECURITY.md).

Jornada ampliada no Chromium confirmou despesa de R$5 e reversão, recuperação física de 10 g (estoque 468), arquivamento/reativação, calendário e comparação. Novo backup `davigurumi-security-20261007` restaurado em `davigurumi_restore_security_20261007`, com objetos privados conferidos por hash e estoque reconciliado sem divergências. A base original foi preservada.
