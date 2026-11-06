# Arquitetura

Monólito modular Django 5.2, Python 3.12, templates HTML/CSS/JavaScript sem framework frontend. PostgreSQL 17 para validar transações/locks/constraints; SQLite opcional para aprendizado local. Há configuração de beta privado no Render Free (`render.yaml`) com PostgreSQL e arquivos privados no Supabase. O estado efetivo dos painéis não foi inspecionado nesta revisão; configuração versionada não comprova qual commit está publicado. `/version/` informa somente o prefixo do commit fornecido pelo Render, ou `unknown` fora desse ambiente.

| App | Responsabilidade |
| --- | --- |
| accounts | Usuário UUID, autenticação, limite de tentativas e espaços demo |
| materials | Cadastros, conversões, camadas, ledger, reservas, idempotência |
| purchasing | Fornecedores, compras, recebimentos e rateio |
| projects | Projetos, revisões, materiais e alternativas |
| pricing | Fórmulas puras em Decimal e calculadora |
| sales | Clientes, versões, snapshots, tokens, portal, PDF e arquivos |
| production | Pedido, consumo vinculado, sessões, correções e entregas |
| finance | Pagamento, alocação, reversão e previsão |
| operations | Notificações, outbox, auditoria, alertas e relatórios |
| portability | Prévia de importação, confirmação e pacote completo |

Serviços concentram operações transacionais. `select_for_update` no usuário serializa operações relacionadas ao mesmo proprietário, simplificando concorrência neste protótipo. Chaves UUID + hash do payload impedem reenvio alterado. Locks reais e triggers adicionais são específicos de PostgreSQL; não existem garantias equivalentes de concorrência no SQLite.

Migrações PostgreSQL protegem vínculos críticos entre proprietários, conteúdo comercial publicado, origem do aceite, imagens publicadas, ledger físico e origem de custos/pagamentos. Elas não substituem autorização por request nem constituem Row Level Security. A exclusão administrativa usa ledger externo assinado e independente do backup do banco; não há retenção automática geral. A barreira de exclusão permanece sem cache negativo e bloqueia acesso quando a verificação falha.

Fotos são verificadas com Pillow, limitadas por bytes/pixels, reencodadas e sem EXIF. Não são servidas por MEDIA_URL público: download passa por autorização do proprietário ou allowlist do snapshot e token. ReportLab gera PDFs públicos preservados no banco. Quotas locais: 100 imagens por usuário, 10 por versão e 5 MB por upload; não são monitoramento de cotas de um provedor.

Sessões/CSRF são Django; CSP permite recursos locais. Portal usa Referrer-Policy same-origin, sem transmitir tokens a outras origens. A decisão passou com formulário nativo no Chromium; no-referrer produziu Origin null e bloqueio CSRF no HTTP de desenvolvimento. Logs Django recebem filtro de redação de URLs do portal. Proxy de produção e seus logs também precisarão desse controle.

Service worker aceita somente allowlist de CSS/JS/ícones; páginas privadas, portal, PDF, imagens e POST nunca entram em cache offline. Não há mutações/sincronização offline. A sessão de produção persiste no servidor, e a tela deriva o cronômetro sem gravação a cada segundo.

Outbox compartilha transação do evento interno, com retentativas e trava no processamento. Entrega externa de e-mail pode duplicar quando servidor aceita a mensagem e a resposta se perde: exatamente uma vez no provedor não é prometido. Não há worker contínuo ou push configurado.

Backups e import/export têm propósitos diferentes: pg_dump+arquivos preserva a instalação; pacote JSON restaura registros de uma conta em destino vazio, revogando capacidades/aceites utilizáveis. Nenhum deles é backup independente/dia sem um operador e agendador configurados.


## Decisão: preservar o monólito modular

Django com templates e aprimoramento progressivo continua sendo a arquitetura
adotada. A revisão de novembro reproduziu consultas repetidas e as corrigiu sem
introduzir SPA, microsserviços ou outro runtime. O ledger de estoque não torna
os demais módulos event sourcing; a dependência do ORM não caracteriza arquitetura
hexagonal estrita.

Reavaliar essa decisão somente após evidência de: equipes independentes bloqueadas
por ciclos de deploy; um domínio com carga desproporcional mesmo após otimização;
ou necessidade comprovada de runtime distinto. Comparar latência, memória, custo
operacional e risco transacional antes de propor migração.

## Consultas, serviços e fronteiras

| Camada / módulo | Contrato e dependências |
| --- | --- |
| `pricing/domain.py` | Cálculo puro em Decimal; sem decisões de persistência ou HTTP. |
| `materials/stock.py` e serviços de materiais | Autoridade para mutações de estoque, reservas, compensações e idempotência. Nenhuma tela grava saldo derivado. |
| `projects` e `sales/services.py` | Fichas/revisões, versões e aceite comercial; alterações posteriores seguem o serviço de aditivo. |
| `production/services.py` | Orquestra produção e integra estoque/comercial pelos serviços existentes; preserva locks e transações. |
| `finance/services.py` | Recebimentos, alocações e reembolsos; não tratar aprovação ou parcela prevista como entrada de dinheiro. |
| `materials/selectors.py`, `production/selectors.py` | Projeções de leitura sem mutações, com somas independentes para não multiplicar valores em joins. |
| `operations/reporting.py` | Leituras deliberadamente atravessam domínios para indicadores e relatórios; não substituem serviços de escrita. |
| `accounts/privacy.py`, `portability` | Orquestração administrativa de exclusão/restauração; deve validar invariantes entre domínios. |
| Views/templates | Autorização por proprietário, validação do formulário, chamada ao caso de uso e apresentação; não duplicar operações transacionais. |

Os serviços públicos existentes continuam responsáveis pela transação e pela
ordem dos locks. Seletores não abrem transações de escrita nem escondem o ORM
atrás de um repositório genérico. A propriedade `effective_seconds` tem fallback
isolado; leituras em lote devem usar `with_effective_seconds()`.

Não dividimos os grandes arquivos de serviços de vendas/produção mecanicamente:
isso não reduz consultas e aumentaria o risco de alterar fronteiras transacionais.
Novos casos de uso podem ser extraídos gradualmente, preservando contratos e testes.

## Operação e medição

Ver `DEPLOY_TESTES_GRATUITO.md` e `RESULTADOS_AUDITORIA_2026_11.md`. A instrumentação
é opcional e não altera configuração publicada. Conexões persistentes têm limite
por ambiente, padrão zero e health checks; o processo continua com um worker e
duas threads. TLS, schema privado e buckets independentes são preservados.

Não há agendador externo demonstrado para outbox, backups, limpeza e monitoramento
de cotas. Continuam tarefas operacionais a configurar e conferir pelo responsável;
a existência de comandos de administração não comprova execução periódica.
