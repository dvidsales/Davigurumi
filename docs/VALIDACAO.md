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

SMTP testado com backend em memória/falha simulada, sem e-mail externo real. O histórico de CI PostgreSQL do PR #2 passou. PRs #1–#3 incorporados; consulte os checks do [PR #4](https://github.com/dvidsales/Davigurumi/pull/4) para execução remota. Não verificados: hospedagem, cobrança/cotas de fornecedor, carga de produção, dispositivos Safari/Android, push, leitor de tela, política legal/exclusão/tombstones e recuperação com perdas reais de infraestrutura.

## Revisão de segurança e novos fluxos

145 testes incluem matriz de isolamento de 45 rotas, limites de arquivos/requisições, configuração WSGI restritiva, cadastro fechado em produção, troca de senha, suspensão/revogação, limpeza de dados transitórios, cotas de prévias, despesas/reversões, compensações de estoque e guardas SQL. Também cobrem aditivos com itens retirados e consumo histórico, calendário, comparação comercial, referências de custo, modelos/importação de metadados e exportação de movimentos.

`pip-audit` não encontrou vulnerabilidades conhecidas nas dependências fixadas. Bandit não encontrou alertas médios ou altos; alertas baixos foram revisados. `check`, verificação de migrações e `pip check` passaram. `check --deploy` com configuração sintética aponta apenas inclusão de subdomínios e preload de HSTS, decisões pendentes do domínio real. Isso não comprova ausência de vulnerabilidades; veja [SECURITY.md](../SECURITY.md).

Jornada ampliada no Chromium confirmou despesa de R$5 e reversão, recuperação física de 10 g (estoque 468), arquivamento/reativação, calendário e comparação. Novo backup `davigurumi-security-20261007` restaurado em `davigurumi_restore_security_20261007`, com objetos privados conferidos por hash e estoque reconciliado sem divergências. A base original foi preservada.

## Continuidade essencial — validação local

Resultado final: **160 testes passaram no PostgreSQL; 155 passaram no SQLite e 5 foram ignorados**. Novos contratos cobrem exclusão completa/arquivo órfão, preservação de outra conta/arquivo, ausência/corrupção do registro externo, bloqueio de pacote antigo e portal/sessão restaurados, reaplicação, mensagens pendentes e cotas de criação/importação/armazenamento. Guardas PostgreSQL permanecem ativos após a manutenção. Expiração de backups testada somente em diretórios temporários; prévia preserva tudo e execução não remove pastas desconhecidas/recentes/com registro adicional.

Chromium conectado somente à base sintética `davigurumi_browser_essentials_20261007`: jornada financeira/estoque completa e 31 telas de 360 px passaram, com zero erros JS/5xx e **zero violações** nas regras automáticas WCAG 2 A/AA e 2.1 AA do axe-core 4.11.0. Cinco telas principais também verificadas a 768 e 1024 px. Corrigidos contraste, foco de áreas roláveis, foco visível, títulos com conteúdo indevido e preservação de botões originalmente desativados ao reconectar. Scanner automático não certifica WCAG nem substitui leitor de tela/dispositivo.

Carga HTTP pequena, autenticada e sintética: 48 leituras, 4 simultâneas, p50 70 ms, p95 104 ms, zero falhas neste cloud. Não mede capacidade comercial ou proteção contra ataques distribuídos. Regressão de consultas testa painel com oito pedidos adicionais e crescimento de no máximo duas consultas; remove consultas repetidas por pedido/material.

`pip-audit` permanece sem vulnerabilidades conhecidas. Bandit sem achados médios/altos; construção de DELETE administrativo usa nomes fixos de modelos permitidos e parâmetros vinculados, com supressão justificada apenas nesse ponto. Checks Django/migrações/sintaxe JavaScript/diff passaram. Ferramentas instaladas isoladamente em `/tmp`; dependências de produção não foram alteradas.

`check_readiness` identifica corretamente configuração de desenvolvimento como não pronta para abertura. Segredos/registro independente, hospedagem, SMTP, TLS/usuário de banco restrito e backup externo continuam dependentes da operação escolhida. A política de retenção necessita aprovação real; testes não estabelecem prazo legal. Roteiro de dispositivos em [TESTES_DISPOSITIVOS](TESTES_DISPOSITIVOS.md).

O código desta continuidade foi enviado para revisão na branch `feat/privacy-and-local-testing`, após autorização do usuário. Nenhum deploy ou merge desta continuidade foi realizado.

## Feedback de interface

164 testes PostgreSQL passaram; SQLite executou 164 com 5 exclusivos ignorados. Novos contratos: cadastro de cliente no orçamento e fornecedor na compra, rollback em dados inválidos, duplicata explícita, busca por ID e autorização dos históricos, orientação da publicação vazia e retorno da biblioteca ao orçamento.

Chromium confirmou a jornada completa até aceite/pedido/quitação, 31 rotas a 360 px, principais a 768/1024 e zero violações WCAG automáticas. Verificação adicional confirmou cadastro integrado de cliente/fornecedor, pesquisa e histórico, orientação do orçamento vazio e exatamente uma opção ativa/aria-current nos menus pedidos, financeiro, dados, relatórios, demonstração e segurança. Conteúdo do pedido/caixa continua dependente de um orçamento com peças e aceite; não removemos essa regra.

Capturas novas, com dados fictícios, em docs/images: materiais-feedback.png, compra-feedback.png e orcamento-feedback.png. Não houve publicação pública ou uso de dados reais.

### Acesso após aceite do cliente

Pedidos agora lista aprovações atuais ainda não convertidas; caixa oferece acesso às aprovações para registrar recebimento. Teste de regressão usa publicação e aceite reais pelo serviço, confirma conversão pela aba de produção, desaparecimento da lista pendente, preservação do acesso financeiro e isolamento entre contas. Aprovar não cria pedido nem pagamento automaticamente. Os 16 testes de usabilidade, produção e financeiro passaram no PostgreSQL e SQLite.

## Conclusão simplificada da encomenda

169 testes passaram no PostgreSQL; SQLite executou 169 com 5 exclusivos ignorados (164 passaram). Quatro novos testes verificam saldo e meio sugeridos, confirmação única com reenvio idempotente, edição parcial sem pagamento implícito, rollback integral quando o recebimento é inválido, revisão desatualizada/assinatura adulterada/peça estrangeira e isolamento entre contas. Nenhum teste anterior foi removido.

Chromium em base sintética confirmou produção/entrega/quitação numa revisão, saldo de 80 após sinal de 20 num pedido de 100, e ausência de pagamento pré-confirmado. Tela a 1440, 768 e 360 px sem overflow, erros JS/5xx ou violações automáticas WCAG 2 A/AA e 2.1 AA; injeção do axe usa bypass CSP apenas no navegador de teste, sem alterar a política da aplicação. Captura com dados fictícios em `docs/images/conclusao-encomenda.png`. Check Django, migrações e Bandit sem achados médios/altos passaram. Sem deploy público.

## Peças direto no orçamento e preenchimento automático

172 testes passaram no PostgreSQL; SQLite passou 167 com 5 exclusivos ignorados. Novos contratos cobrem criação integrada sem ficha anterior, reaproveitamento do preço proporcional, manutenção de custos desconhecidos/aceite da limitação na publicação, sugestão calculada por quantidade, isolamento, dados inválidos, duplicata e bloqueio de criação em versão publicada sem peça órfã. Migração aditiva `projects.0003_projectrevision_quick_entry`.

Chromium em base sintética confirmou cadastro direto, descrição e preço preenchidos pela biblioteca, recálculo ao mudar quantidade e preservação de preço editado manualmente. Tela em 1440, 768 e 360 px sem overflow, erros JS/5xx ou violações automáticas WCAG. Captura fictícia em `docs/images/peca-direto-orcamento.png`. Check Django, migrações, sintaxe JS, diff e Bandit sem achados médios/altos passaram. Sem deploy público.

## Interface e navegação entre etapas

175 testes PostgreSQL passaram; SQLite passou 170 com 5 exclusivos ignorados. Novos testes cobrem acesso às quatro etapas no rascunho vazio, condições editadas salvas, leitura de versão publicada sem alterar seu hash, isolamento e rotas inválidas/método POST bloqueado. Corrigidos campos extras de cliente enviados indevidamente ao serviço de edição das condições.

Chromium confirmou percurso 1 → 2 → 3 → 4 → 2 e cinco páginas (incluindo versão aprovada/publicada) a 1440, 768 e 360 px, sem overflow, erros JS/5xx ou violações automáticas WCAG. Capturas fictícias em `docs/images/orcamento-etapas.png` e `docs/images/financeiro-acoes.png`. Botões editar/remover alinhados; ações e registros financeiros separados com espaçamento. Check/migrações/diff e Bandit sem achados médios/altos passaram. Sem nova migração ou deploy público.


## Revisão e beta privado — 08/10/2026

186 testes aprovados no PostgreSQL. SQLite: 186 executados, 181 aprovados e 5 exclusivos do PostgreSQL ignorados. Novas regressões: convite por e-mail, bloqueio de convite inválido, proxy/IP, saúde sem detalhes, armazenamento privado remoto, indisponibilidade/bucket público, exclusão assinada e arquivos órfãos, exportação/restauração remota, erro de desconto, preço calculado preservado, produção sem pagamento confirmado, recuperação sem SMTP e imagem indisponível com isolamento entre contas.

Chromium: jornada completa com orçamento de 63, sinal de 20 e saldo de 43, estoque/produção/entrega/recebimento, exportações e imports, isolamento e demonstração. 31 telas sem overflow a 360 px, verificações a 768/1024 px, zero erros JS/5xx e zero violações detectadas pelo axe. Carga local descartável: 48 requisições concorrência 4, p50 72 ms/p95 301 ms, zero falhas; isso não estima capacidade no plano gratuito.

Gunicorn com DEBUG desligado: login, CSS com manifesto, cookie seguro, saúde, redirecionamento HTTPS, cadastro fechado e recuperação indisponível verificados. Migrations completas em schema privado e papel sem privilégios administrativos passaram no PostgreSQL local; TLS desse banco local é desativado apenas na interface de loopback. Deploy exige verify-full. Check/migrações, sintaxe JS/Bash, auditoria de dependências sem vulnerabilidades conhecidas e Bandit sem achados médios/altos passaram. Nenhum teste ou alerta foi removido para obter aprovação.

O protocolo Supabase foi simulado, não validado contra uma conta real. Render/Supabase não foram provisionados; disponibilidade/preços dos planos não puderam ser confirmados devido ao bloqueio de rede. Falta ativar suas contas e executar o roteiro de verificação do [deploy gratuito](DEPLOY_TESTES_GRATUITO.md), além dos testes em dispositivos reais. Uso público não está liberado.

Verificação final do service worker em configuração de produção: URLs de CSS/JS correspondem ao manifesto versionado, preservando a lista explícita de arquivos públicos.
