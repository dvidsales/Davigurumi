# Resultado dos ajustes da auditoria — 5 de novembro de 2026

## Escopo e rastreabilidade

Implementação local na branch `perf/auditoria-consultas-ux`, partindo do commit
`79b0de710bec4bb6e8df696cedd730744ac497a3` (mesma árvore do checkout inicial
`1bd0e32`). Foram lidos os dois documentos anexados e confirmados os achados.
Não houve push, publicação, alteração de painel, acesso com credenciais reais,
mutação no beta ou mudança do banco de produção.

Ambiente: Python 3.12.14, Django 5.2.18, psycopg 3.3.6, PostgreSQL 17.11 local,
Chromium e Playwright 1.62.1, axe-core 4.11.0. Banco e arquivos dos testes de UI
são descartáveis (`davigurumi_audit_ui_20261105`, `.local/audit_ui_files`). As suítes
Django criam/removem seus próprios bancos de teste. SQLite é complementar.
O documento anterior `AVALIACAO_LINGUAGEM_E_MEMORIA.md` foi preservado como estava.

## Alterações implementadas

| Achado / pedido | Entrega e limite |
| --- | --- |
| Correções de tempo ignoravam prefetch | `ProductionSessionQuerySet.with_effective_seconds()` usa subconsulta escalar ordenada por `-created_at, -id`. Zero é preservado e ausência usa `seconds`; acesso isolado continua funcionando. Aplicado a custos, agenda e detalhe do pedido. |
| Reservas por item | Uma consulta com referências dos itens e owner, agrupada em memória; custos de camadas desconhecidas continuam incompletos. Não foi alterada a ordem de locks nem a escrita. |
| Sem planejamento | Relação orçamento carregada em lote e sem PDF/snapshots; quadro explicitamente global, independente dos filtros da agenda. Sem início E sem prazo de produção; entrega comercial não substitui planejamento. |
| Relatório ilimitado | 25 pedidos por página, ordem determinística do modelo, período efetivo e filtros preservados; exportação completa dos filtros continua limitada a 5.000 pedidos, independentemente da página. |
| Campos pesados | PDF e snapshots diferidos em relatórios, listas de orçamentos/pedidos, versões aprovadas de caixa/produção e agenda. Teste confirma acesso a total/saldo sem consultas tardias. |
| Históricos materializados | Indicador de saldo usa subconsultas independentes de pagamentos/reembolsos. Estoque disponível para reposição/mínimo usa somas independentes de movimentos e reservas das camadas. Caixa global agrega valores no banco. Não há saldo redundante persistido. |
| Formulário inválido parecia vazio | Relatório geral separa erro de resultado válido vazio, sem exportar dados inválidos. |
| Consistência de filtros | Período compartilhado entre agenda/relatório geral, filtros adicionais nativos, limpar e exportações separadas. Rótulos de peça alinhados. Movimentos conserva seu filtro de material e a mesma convenção de período. |
| Início com competição de indicadores | Cronômetro preservado; bloco de tarefas com vencidos, próximos prazos de produção, respostas e reposição antes dos indicadores. Cadastros recolhidos, período do caixa explícito e sem sugerir lucro. |
| Custo por embalagem | Auxiliar opcional no cadastro inicial: preço, quantidade na unidade base e prévia indicativa. Cálculo definitivo Decimal com arredondamento half-up a seis casas; custo zero e desconhecido distintos. Não cria compra, não altera a quantidade inicial nem o ledger existente. |
| Service worker / manifest | Confirmado que `config.pwa` já resolvia nomes com hash: não era defeito de allowlist no build. Agora o namespace do cache também deriva dos assets, evitando que instalações diferentes compartilhem o mesmo cache. Sem skipWaiting ou cache de páginas privadas/POST. |
| Dependências | Pillow 12.3.0 → 13.0.0 após a checagem atual indicar registros de vulnerabilidade na versão anterior. Testes de imagens e fluxos repetidos. |
| Identificação de deploy | `/version/` retorna somente os primeiros 12 caracteres de `RENDER_GIT_COMMIT`, validado como SHA hexadecimal de 40 caracteres; fora do Render retorna `unknown`. Não expõe configuração. |
| Observabilidade e conexões | Instrumentação agregada opt-in, sem SQL/URLs/dados sensíveis. Persistência de conexão configurável, limitada a 0–300 s, padrão 0 e health checks. Nenhum valor foi ativado no provedor. |

Não houve nova migração. Imutabilidade de versões, idempotência, CSRF, arquivos
privados, ledger externo e integridade financeira/estoque mantêm seus serviços e
restrições. A suíte integral continua cobrindo seus contratos existentes.

## Consultas: antes e depois

| Experimento sintético | Antes | Depois |
| --- | --- | --- |
| Soma de tempo, 1 / 10 / 50 sessões | 3 / 12 / 52 | 1 / 1 / 1 |
| `cost_summary`, 50 sessões | 57 | 6 |
| Custos com reservas, 1 / 20 itens | 6 / 25 | 6 / 6 |
| Detalhe com 1 / 50 sessões, após aquecimento | Não medido com esse protocolo antes | 19 / 19 |
| Agenda de pedidos sem planejamento, 1 / 10 pedidos, após aquecimento | Crescimento confirmado; coleta inicial incluía inicialização no primeiro acesso | 12 / 12 |

As regressões cobrem zero/uma/múltiplas correções, empate de timestamp, correção
zero, sessão ativa/encerrada, custo decimal, reservas parciais, item retirado,
custo desconhecido e reserva de outro proprietário. Não preenchemos caches
privados do ORM. Pagamentos com múltiplos reembolsos e cancelamentos são comparados
ao cálculo de referência; consumo/compensação/reservas ao ledger de estoque.

## Comparação local de rotas

30 amostras aquecidas por rota, uma conta, um pedido planejado com 50 sessões,
mesmo PostgreSQL local e mesmo ambiente Python/dependências (incluindo Pillow 13)
para ambas as árvores de código. Cada rota aquece antes da coleta. Bancos de teste
separados para antes/depois. Clientes sintéticos separados por rota respeitam a
quota de leitura, sem desativar limites. As rotas não são o beta publicado.

| Rota | Consultas antes → depois | Mediana ms | p95 ms | Máximo de bytes HTML |
| --- | --- | --- | --- | --- |
| `/` | 27 → 26 | 44.88 → 48.76 | 83.64 → 62.1 | 16458 → 17332 |
| `/materiais/` | 7 → 7 | 17.37 → 14.4 | 27.71 → 17.49 | 16145 → 16145 |
| `/orcamentos/` | 5 → 5 | 12.28 → 11.84 | 20.47 → 15.32 | 15010 → 15010 |
| `/pedidos/` | 7 → 7 | 16.34 → 19.71 | 22.55 → 25.2 | 15321 → 15321 |
| `/pedidos/calendario/` | 65 → 14 | 103.42 → 33.42 | 164.95 → 45.56 | 18512 → 18576 |
| `/notificacoes/relatorios/` | 22 → 21 | 45.63 → 44.77 | 56.89 → 51.91 | 17644 → 18522 |

Medições do test client incluem aplicação/instrumentação SQL local, mas excluem
navegador, rede pública, banco remoto, ledger remoto, TLS e cold start do Render.
O volume informado é da resposta HTML, não bytes transferidos pelo PostgreSQL.
Campos diferidos têm comprovação por ORM/testes; tráfego de banco em bytes não foi
medido. Não inferir ganho percentual de produção. Algumas medianas aumentaram;
a melhora comprovada é na quantidade de consultas e no trabalho limitado por
página. O objetivo de p95 ≤ 800 ms em homologação remota permanece não verificado.

Os EXPLAINs de sessões e estoque constam no JSON depois. A fixture pequena usa
scans e índices existentes de FK; não justifica acrescentar índices arbitrários.
Reavaliar com cardinalidade representativa antes de criar índice composto para
correções ou alterar estratégia de planejamento.

## Validação executada nesta intervenção

- Baseline: 190 testes PostgreSQL aprovados, nenhum pulado.
- Após os ajustes/Pillow: 210 testes PostgreSQL aprovados, nenhum pulado.
- SQLite: 210 descobertos, 205 aprovados e cinco pulados, específicos de
  triggers/concorrência PostgreSQL. Não substitui o resultado acima.
- `check`, migrações sem drift, sintaxe dos três scripts de navegador e JS do app,
  `collectstatic` com manifest e check de deploy passaram. Este último conserva
  W005/W021: não ativamos HSTS de subdomínios/preload sem avaliar domínio.
- `smoke_mobile.cjs`: 14 rotas × oito larguras = 112 verificações de overflow;
  nove casos axe (incluindo erro no relatório e auxiliar de embalagem), foco,
  Escape, teclado, formulário preservado, texto 200%, orientação horizontal,
  redução de movimento e fallback sem JS.
- `review_audit_ui.cjs`: 32 combinações com dados extensos (27 pedidos), oito casos
  axe em 390/1440 px, paginação/filtros e falha de rede com rascunho preservado.
- `smoke_browser.cjs`: fluxo completo com 31 rotas, 360/768/1024 px, zero erros
  JavaScript/5xx inesperados e nenhuma violação nos casos axe cobertos. Inclui
  sinal transferido uma vez, consumo, recuperação, despesa/reversão, compra,
  aceite, entrega/recebimento, XLSX, segunda conta e espaço demo. Carga opcional
  desse script não foi habilitada (`load: null`).
- Build com manifest em servidor local separado: quatro assets com hash,
  recuperação offline de CSS e indisponibilidade offline da página privada.
- `pip-audit -r requirements.txt`: nenhum registro de vulnerabilidade conhecido
  depois da atualização; Bandit `-ll`: nenhum achado no limiar configurado.
- Configuração com `POSTGRES_CONN_MAX_AGE=60`: quatro testes de configuração
  aprovados localmente; não equivale a teste de pooler/conexão ociosa no Supabase.

Erros 4xx/503 esperados aparecem em testes negativos. As primeiras execuções de
regressão falharam no código antigo como esperado. O smoke completo exigiu ajuste
para abrir características pelo rótulo (o novo auxiliar mudou a posição do details)
e para trocar datas fixas de outubro pela data atual; foram mantidas as asserções.

Não foi criada nem consultada CI nova nesta intervenção. As evidências de CI no
relatório recebido são históricas. Nenhum resultado acima é atribuído a essa CI.

## Evidências e capturas

JSONs reproduzíveis em [evidencias/auditoria-2026-11](evidencias/auditoria-2026-11/):
benchmark antes/depois, planos PostgreSQL, mobile, interface com dados, fluxo e
manifest. São somente dados sintéticos e métricas agregadas.

- [Início móvel](images/auditoria-2026-11/inicio-390.png)
- [Relatório com dados](images/auditoria-2026-11/relatorios-1440.png)
- [Erro de filtros no celular](images/auditoria-2026-11/relatorios-invalidos-390.png)
- [Agenda móvel](images/auditoria-2026-11/agenda-390.png)

## Pendências explícitas

1. Medir ledger/armazenamento e conexões no ambiente remoto autorizado. Não há
   credenciais remotas neste ambiente; a barreira não foi reduzida. Ver
   [LEDGER_E_OBSERVABILIDADE.md](LEDGER_E_OBSERVABILIDADE.md).
2. Coletar homologação remota/cold start e métricas reais de navegador. Não foram
   medidos LCP/INP/CLS de campo, capacidade simultânea ou Safari/iPhone/leitor de
   tela. Axe não certifica acessibilidade completa.
3. Reposição ainda lê os consumos necessários e snapshots dos itens para preservar
   compensações e necessidades. A otimização agrega estoque físico/reservado;
   não elimina toda materialização nem impõe paginação às necessidades globais.
4. Grandes arquivos de serviços não foram divididos artificialmente. Extrações
   futuras por caso de uso devem preservar transações; seletores foram separados
   onde havia benefício concreto. Não há adoção de cache ou infraestrutura nova.
5. Outbox, backups externos, tarefas periódicas e cotas dos provedores continuam
   dependentes de operação; não foram provisionados nem homologados aqui.

## Reproduzir

No ambiente de desenvolvimento já configurado, sem importar `.env` de produção:

```bash
bash scripts/dev_postgres.sh
bash scripts/with_postgres.sh manage.py check
bash scripts/with_postgres.sh manage.py makemigrations --check --dry-run
bash scripts/with_postgres.sh manage.py test --noinput
DAVIGURUMI_TEST_DB=audit_after bash scripts/with_postgres.sh scripts/benchmark_reads.py --output /tmp/benchmark.json
```

O benchmark cria/remove seu banco de testes e recusa menos de 30 amostras. Para
comparar antes, exportar `git archive 79b0de7` para diretório temporário separado,
copiar o benchmark e sua fixture `production/test_read_queries.py` e usar o mesmo
Python/dependências. Não executar o benchmark contra um banco compartilhado:
o papel local precisa de permissão para criar o banco temporário de testes.

Revisão visual: criar um PostgreSQL **vazio, local e descartável** com prefixo
`davigurumi_audit_ui_`, migrá-lo, executar uma vez `scripts/seed_audit_review.py`
com `DAVIGURUMI_SMOKE_ISOLATED=1` e iniciar o app nesse banco. A fixture recusa
host remoto/nome não marcado. Conta e senha no script são exclusivamente
sintéticas. Para este ambiente, usar `DAVIGURUMI_TEST_DB` com `with_postgres.sh`.
Não reutilizar o nome de um banco existente para resetá-lo.

Instalar Playwright 1.62.1 e axe-core 4.11.0 em diretório de ferramentas; os scripts
usam Chromium disponível no host. Com o servidor isolado em 8120, executar
**sequencialmente**, respeitando a quota normal entre repetições:

```bash
export DAVIGURUMI_SMOKE_ISOLATED=1
export DAVIGURUMI_SMOKE_URL=http://127.0.0.1:8120
export DAVIGURUMI_AXE_PATH=/tmp/davigurumi-browser-tools/node_modules/axe-core/axe.min.js
node scripts/smoke_mobile.cjs
node scripts/smoke_browser.cjs
node scripts/review_audit_ui.cjs
```

A variável não transforma um banco real em descartável. Nunca apontar esses
scripts para o beta. Sem `DAVIGURUMI_AXE_PATH`, os smokes antigos podem pular axe;
nesta intervenção ela estava configurada. `review_audit_ui.cjs` exige axe.

## Rollback e implantação

Nenhuma implantação foi feita. Não há migração nem formato persistido novo para
reverter. Para desfazer as mudanças, revisar/reverter o commit aplicativo na
branch, preservando o commit separado de atualização do Pillow 13 e as proteções
de exclusão. Não restaurar banco, apagar ledger ou trocar sua chave para rollback.
Conferir suite e manifest depois da reversão e usar deploy manual somente após
revisão. `POSTGRES_CONN_MAX_AGE=0` mantém o padrão; desabilitar métricas é retornar
`DJANGO_PERFORMANCE_LOGGING` a 0. Não há mudança obrigatória de plano pago.
