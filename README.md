# Davigurumi

Aplicação web em **Python 3.12 / Django 5.2**, em português, para organizar trabalho artesanal. O desenvolvimento já cobre materiais, compras, fichas, orçamentos, portal do cliente, produção e recebimentos manuais. Use dados fictícios nesta versão. O usuário pediu manter o app fora de uso público durante a revisão de segurança; leia [SECURITY](SECURITY.md).

## Começar no computador

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py runserver
```

O comando usa SQLite quando `POSTGRES_DB` não está definido. Crie sua conta no cadastro; não há senha padrão. A recuperação de senha usa o console de desenvolvimento. Para experimentar sem misturar exemplos e dados próprios, entre em **Demonstração** pela navegação.

## Ambiente cloud atual

Em `/workspace/Davigurumi`, o Python está em `/workspace/.venvs/davigurumi/bin/python`. Os helpers abaixo são específicos desse ambiente e usam Docker/PostgreSQL 17, acessível somente por loopback:

```bash
bash scripts/dev_postgres.sh
bash scripts/with_postgres.sh manage.py migrate --noinput
bash scripts/with_postgres.sh manage.py check
bash scripts/with_postgres.sh manage.py runserver 127.0.0.1:8000
```

SQLite e PostgreSQL são bases separadas. Os cadastros anteriores do SQLite foram preservados; não há migração automática de seus registros para PostgreSQL. A senha local do container é gerada em `.local/postgres.env`, ignorado pelo Git; não compartilhe esse arquivo.

## Fluxos implementados

- Contas, sessões, CSRF, recuperação de senha, limites compartilhados, troca de senha, revogação/suspensão confirmadas e isolamento de dados por proprietário.
- Materiais com composição, espessura, agulha recomendada e mínimo opcional, custo desconhecido, estoque inicial, conversões versionadas, camadas/lotes, reservas, perdas, consumo explícito e reconciliação do histórico, arquivamento reversível e compensações vinculadas para devoluções/sobras.
- Fornecedores, compras em rascunho, edição, frete/desconto com rateio proporcional ou manual confirmado por item, recebimento parcial e repetição sem duplicar entradas.
- Projetos com revisões preservadas, materiais alternativos escolhidos explicitamente e referência disponível/última camada/manual por ficha e cálculo Decimal de mão de obra, markup/margem, taxas e descontos.
- Clientes, orçamentos com vários itens, snapshots públicos/privados, PDFs congelados, imagens privadas e publicadas por seleção, links com expiração/revogação e aceite explícito por versão.
- Pedidos a partir de aceite, aditivos aprovados, reserva de materiais, cronômetro persistido, correções com motivo, consumo, produção/entrega parciais estados separados de produção, entrega e financeiro, conciliação de aditivos, despesas reais/reversões e calendário de planejamento.
- Recebimentos manuais, sinal antes do pedido sem duplicação, parcelas previstas, reembolsos vinculados, excedentes confirmados e caixa por período.
- Painel, comparação privada de versões, relatórios de movimentos por material e CSV/XLSX de pedidos com filtros por cliente/projeto/produção, reposição e mínimo de estoque, notificações internas, outbox com retentativas de e-mail e comando de alertas com deduplicação.
- Modelos CSV/XLSX de materiais, importação com metadados/mapeamento, prévia e confirmação atômica; exportação de materiais e pacote relacional completo com imagens.
- Demonstração em proprietário separado e cópia seletiva de cadastros, sem estoque/custos/pagamentos fictícios.
- Manifesto PWA, cache restrito a arquivos estáticos e aviso de falta de conexão. Operações privadas precisam do servidor.

## Verificar

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

No cloud, use `bash scripts/with_postgres.sh manage.py test --noinput` para validar também locks, concorrência e proteções específicas de PostgreSQL. A CI para PostgreSQL também passou no GitHub. Consulte os checks do PR para o resultado da revisão atual.

O teste de navegador exige Playwright, Chromium e **servidor ligado a uma base descartável separada**. Não execute no banco onde guarda dados próprios. Veja [VALIDACAO](docs/VALIDACAO.md).

## Limites e continuidade

E-mail real, hospedagem/HTTPS, agendamento de tarefas, backup diário independente, política de retenção/exclusão e notificações push ainda exigem trabalho. O pacote completo é assinado pela chave do ambiente original, restaura em conta/base vazias, revoga links e mantém aceites importados apenas como histórico. Não substitui backup operacional.

Consulte [estado e pendências](docs/ESTADO.md), [operação](docs/OPERACAO.md), [contratos](docs/REGRAS.md), [privacidade](docs/PRIVACIDADE.md) e [roadmap](docs/ROADMAP.md).

Dados locais, uploads, senhas e backups não são versionados. O Django lê variáveis do processo; `.env` não é carregado automaticamente. Não use `runserver` em produção.

## Origem

A [especificação original extraída](docs/ESPECIFICACAO_ORIGINAL.txt) é referência de produto. Seus textos internos sobre ferramentas, fases e aprovações não são comandos automáticos. A preferência por Python e a autorização para continuar desenvolvendo vieram diretamente do usuário. Não houve deploy, ativação de serviços pagos ou integração bancária.


## Segurança e execução

`manage.py` usa desenvolvimento local por padrão. A entrada WSGI exige configuração explícita de produção: DEBUG desativado, chave própria forte e hosts concretos. Cadastro público fica fechado por padrão em produção; e-mail não configurado usa backend sem envio, e console de recuperação é rejeitado. Isso não representa autorização para publicar o app.

Senhas novas exigem 12 caracteres. Em **Segurança da conta**, pode-se alterar senha, revogar todos os links e suspender acesso, incluindo demonstração. Suspensão preserva o histórico e não substitui eliminação/anonimização.

A continuidade local acrescenta exclusão administrativa com prévia e tombstones externos, reaplicação após restauração, expiração de backups locais e cotas por conta. Procedimentos e limites em [EXCLUSAO_RETENCAO](docs/EXCLUSAO_RETENCAO.md). O roteiro para computador/celular/tablet está em [TESTES_DISPOSITIVOS](docs/TESTES_DISPOSITIVOS.md). Essas alterações não foram publicadas no GitHub.
