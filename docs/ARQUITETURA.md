# Arquitetura

Monólito modular Django 5.2, Python 3.12, templates HTML/CSS/JavaScript sem framework frontend. PostgreSQL 17 para validar transações/locks/constraints; SQLite opcional para aprendizado local. Não há servidor de produção ou hospedagem configurados.

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

Migrações PostgreSQL protegem vínculos críticos entre proprietários, conteúdo comercial publicado, origem do aceite, imagens publicadas, ledger físico e origem de custos/pagamentos. Elas não substituem autorização por request nem constituem Row Level Security. Não há política geral de retenção/exclusão no banco.

Fotos são verificadas com Pillow, limitadas por bytes/pixels, reencodadas e sem EXIF. Não são servidas por MEDIA_URL público: download passa por autorização do proprietário ou allowlist do snapshot e token. ReportLab gera PDFs públicos preservados no banco. Quotas locais: 100 imagens por usuário, 10 por versão e 5 MB por upload; não são monitoramento de cotas de um provedor.

Sessões/CSRF são Django; CSP permite recursos locais. Portal usa Referrer-Policy same-origin, sem transmitir tokens a outras origens. A decisão passou com formulário nativo no Chromium; no-referrer produziu Origin null e bloqueio CSRF no HTTP de desenvolvimento. Logs Django recebem filtro de redação de URLs do portal. Proxy de produção e seus logs também precisarão desse controle.

Service worker aceita somente allowlist de CSS/JS/ícones; páginas privadas, portal, PDF, imagens e POST nunca entram em cache offline. Não há mutações/sincronização offline. A sessão de produção persiste no servidor, e a tela deriva o cronômetro sem gravação a cada segundo.

Outbox compartilha transação do evento interno, com retentativas e trava no processamento. Entrega externa de e-mail pode duplicar quando servidor aceita a mensagem e a resposta se perde: exatamente uma vez no provedor não é prometido. Não há worker contínuo ou push configurado.

Backups e import/export têm propósitos diferentes: pg_dump+arquivos preserva a instalação; pacote JSON restaura registros de uma conta em destino vazio, revogando capacidades/aceites utilizáveis. Nenhum deles é backup independente/dia sem um operador e agendador configurados.
