# Arquitetura e alternativas

## Entendimento

O produto integra materiais → compras/estoque → projetos/ficha → precificação →
orçamentos versionados → aceite → pedido → produção/consumo → recebimentos.
Atende várias técnicas, sem exigir empresa ou equipe. Histórico, isolamento,
precisão e cadastro progressivo são requisitos transversais.

## Alternativas consideradas

| Alternativa | Vantagens | Custos e limitações |
| --- | --- | --- |
| A. Django + templates + PostgreSQL | Regras em Python, autenticação mantida, migrations, formulários/CSRF; uma aplicação para manter | Exige hospedagem de processo Python, arquivos privados, worker e SMTP; gratuidade pública não garantida |
| B. FastAPI + React + PostgreSQL | Python no backend, API independente, frontend flexível | Dois projetos/toolchains; mais integração de auth, formulários, sessões e acessibilidade |
| C. React + Supabase, proposta do PDF | Auth, PostgreSQL/RLS e storage gerenciados | Menos Python; regras em SQL/TypeScript; cotas, SMTP e backup externo ainda precisam de validação |

**Escolha de implementação nesta entrega: A**, pela preferência por Python e menor
complexidade operacional. É uma escolha técnica reversível para desenvolvimento;
não é aprovação de hospedagem ou de todas as regras propostas no documento.

Frontend renderizado pelo servidor, HTML semântico e CSS local, sem fontes/scripts
externos. JavaScript poderá ser acrescentado para cronômetro, PWA e interações que
precisem dele; não é necessário transformar tudo em SPA. Python concentra regras
de domínio e transações. SQLite é só para a primeira fatia local; PostgreSQL será
exigido e testado antes de reservas e consumo concorrentes.

## Estrutura atual

```text
config/      configurações, rotas, WSGI
accounts/    usuário, cadastro, visão geral e testes
materials/   materiais, abertura de estoque, serviço atômico, migrations e testes
pricing/     funções Decimal independentes, formulário e testes
templates/   apresentação em pt-BR
static/css/  identidade provisória e responsividade
docs/        especificação, decisões, plano e evidências
```

Não criar apps vazios para todos os módulos futuros. Separar domínio de apresentação
quando houver regra real: `pricing/domain.py` é puro; `materials/services.py` coordena
persistência. Views obtêm proprietário da sessão, nunca do formulário.

## Modelo atual e desenho do restante

`User(UUID)` possui `Material(UUID)`; `Material` possui uma entrada inicial
`StockMovement(UUID)`. Movimento herda propriedade pelo material, evitando duas
autoridades de ownership. Unicidade `(owner, request_key)` impede reenvio; quantidade
positiva, custo não negativo/nulo e entrada única são constraints do banco.

O modelo de abertura será evoluído por migration para movimentos tipados e camadas,
sem apagar ou reinterpretar saldos existentes. Não há reserva, débito ou edição de
movimentos pela aplicação atual. Não se afirma imutabilidade contra SQL direto.

| Domínio futuro | Entidades/vínculos | Constraints e operação atômica |
| --- | --- | --- |
| Unidades | Unit, MaterialConversion → material/apresentação | Dimensão compatível, fator positivo, fator/versionamento congelado |
| Compras | Supplier → Purchase → itens → recebimentos → camadas; lote de fabricação separado | Vínculos do mesmo dono, recebimento ≤ contratado; receipt + movimento + custo juntos; chave idempotente |
| Estoque | camada → movimentos; reserva → alocações | Lock de camadas em ordem estável; físico ≥ reservado ≥ 0; compensações referenciadas |
| Projetos | Project → revisões → linhas → alternativas | Quantidade-base positiva; escolha de alternativa explícita; revisão copiada, não só FK |
| Comercial | Client; Quote → versões → itens e imagens | Número por dono; uma vigente; conteúdo publicado imutável; snapshots privado/público separados |
| Portal | token hash → versão; eventos/aceite | Token aleatório de 256 bits; validade/revogação; POST explícito; decisão terminal única por versão |
| Pedidos | aceite → pedido → itens/aditivos/entregas | Pedido único por aceite; condição comercial versionada; entrega parcial ≤ contratada |
| Produção | sessões → pedido/item; consumo → camada/movimento | Uma sessão ativa por usuário como proposta; timestamps do servidor; consumo explícito transacional |
| Financeiro | cobranças; recebimentos → alocações; estornos → recebimento | Alocar uma vez, estornar no máximo líquido; previsão não é caixa |
| Operação | outbox, notificações, arquivos, auditoria, jobs | Evento/outbox na mesma transação; chave evento/destinatário/canal; arquivos autorizados |

Registros privados futuros usam proprietário da sessão. Vínculos devem ser protegidos
por constraints compostas ou validação transacional equivalente. IDs UUID não substituem
autorização. Ainda não há RLS; filtros Django atuais foram testados, não constituem
prova de isolamento de tabelas futuras.

## Arquivos, PDF, mensagens e PWA

- Arquivos privados fora de `static/`; downloads passam por autorização ou URL assinada
  curta. Upload JPEG/PNG/WebP: proposta de 5 MB, limite de pixels, validação real e EXIF
  removido. SVG/HTML não serão uploads aceitos. Nenhum upload existe nesta entrega.
- PDF nasce de projeção pública allowlist, com snapshot/versão do gerador. ReportLab
  é candidato Python: validar imagens, múltiplas páginas e ausência de campos privados
  antes de escolher/travar dependência. Não houve protótipo de PDF nesta etapa.
- Outbox no banco e comando agendado/worker, sem Redis/Celery obrigatório no início.
  SMTP transacional e Web Push exigem configuração posterior; falha externa não desfaz
  transação principal. Console atual não é canal de produção.
- PWA: manifesto, ícones e service worker futuro com cache apenas de estáticos públicos;
  nunca APIs, HTML privado, portal, imagens ou exports. Logout deverá limpar caches e
  estado local. A entrega atual é web responsiva, **ainda não é PWA instalável**.
- Templates com labels, landmarks, foco visível e alvos mobile. Revisão manual de
  teclado/leitor de tela e WCAG 2.2 AA permanece necessária.

## Acesso e ameaça

Sessões Django com senhas hash, CSRF e templates com escape padrão. E-mail único
case-insensitive no banco. Recuperação usa token do framework, invalidado após troca.
Antes de acesso público: rate limiting, verificação de e-mail, política de conta,
SMTP, TLS, secrets de produção, CSP, quotas, tratamento de incidentes e testes de
isolamento com PostgreSQL. Não expor arquivos privados via servidor de estáticos.

## Direções visuais propostas

1. **Clareza verde:** branco, verde profundo, acento sálvia; painel sóbrio. Usada
   provisoriamente nesta entrega, com cores centralizadas nas variáveis CSS.
2. **Precisão azul:** fundo neutro, azul-marinho e acento azul; maior aparência técnica.
3. **Editorial areia:** off-white, grafite e terracota comedida; contraste AA a verificar.

Nenhuma direção foi declarada aprovada pelo usuário. Marca textual substituível,
sem usar motivos artesanais como decoração dominante.
