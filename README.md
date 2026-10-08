# Davigurumi

Aplicação web em **Python 3.12 / Django 5.2**, em português, para organizar trabalho artesanal. O desenvolvimento já cobre materiais, compras, fichas, orçamentos, portal do cliente, produção e recebimentos manuais. Use dados fictícios nesta versão. O usuário pediu manter o app fora de uso público durante a revisão de segurança; leia [SECURITY](SECURITY.md).

## Testar no VS Code

Pré-requisitos: **Python 3.12**, VS Code e a extensão **Python** da Microsoft. Para começar, SQLite é suficiente: não precisa instalar Docker ou PostgreSQL. Os testes de locks/triggers de produção usam PostgreSQL separadamente.

Abra no VS Code a pasta do código que contém `manage.py` (`Arquivo → Abrir Pasta`). Se estiver usando o pacote local disponibilizado no chat, extraia-o em **uma pasta nova**, sem sobrescrever seu checkout ou dados existentes. Os ajustes de interface anteriores já estão na `main`. A conclusão simplificada já está na `main`. O cadastro de peças no orçamento já está na `main`. Os ajustes de interface e navegação entre etapas estão na branch `feat/interface-and-quote-navigation`, aguardando revisão. Depois de atualizar o código, execute `python manage.py migrate` para aplicar a nova migração.

Abra `Terminal → Novo Terminal` e confira a versão:

```bash
python --version
```

### Windows — PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Não é necessário ativar o venv ou alterar a política de execução do PowerShell. Se o comando `py` não existir, use `python -m venv .venv` depois de confirmar que `python --version` mostra 3.12.

### macOS ou Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Se sua instalação disponibiliza Python 3.12 como `python3`, use `python3 -m venv .venv` após conferir a versão.

### Abrir e experimentar

No VS Code, use `Ctrl+Shift+P` (macOS: `Cmd+Shift+P`) → **Python: Select Interpreter** e selecione o Python da `.venv`. Abra **http://127.0.0.1:8000** no navegador do computador. Mantenha o terminal do servidor aberto; para parar, use `Ctrl+C`.

Crie sua conta em **Criar conta**; não há senha padrão. Use uma senha de pelo menos 12 caracteres e dados fictícios. Comece pelo menu **Demonstração**, que mantém exemplos separados dos seus cadastros. Depois siga o [roteiro de testes](docs/TESTES_DISPOSITIVOS.md).

SQLite guarda dados em `.local/db.sqlite3`; uploads ficam em `.local/files`. Não apagar essas pastas para atualizar o app ou resolver um erro. `migrate` atualiza a estrutura; não é preciso executar `makemigrations` para testar. O código não carrega `.env` automaticamente e, para esse teste local básico, não é necessário copiar ou configurar esse arquivo. Se já houver `POSTGRES_DB` nas variáveis do terminal, o Django usará PostgreSQL em vez de SQLite.

Recuperação de senha usa o console do servidor no desenvolvimento: o link aparece no terminal e não é enviado para seu e-mail. Não compartilhar esse link. Não executar os comandos administrativos de exclusão/expurgo com `--apply` para experimentar a interface.

Se a porta 8000 estiver ocupada, use `runserver 127.0.0.1:8001` e abra essa porta no navegador. Se aparecer erro, copie a mensagem e o comando executado, sem senhas/segredos. Para testar no celular, siga a orientação de endereço privado/HTTPS do roteiro; `127.0.0.1` no celular aponta para o próprio celular.

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

No cloud, use `bash scripts/with_postgres.sh manage.py test --noinput` para validar também locks, concorrência e proteções específicas de PostgreSQL. A etapa publicada teve CI PostgreSQL aprovada no GitHub. A revisão mais recente passou 175 testes PostgreSQL e 170 SQLite, com 5 específicos ignorados; ela está na branch `feat/interface-and-quote-navigation`, aguardando revisão. Consulte [VALIDACAO](docs/VALIDACAO.md) para distinguir as evidências locais e remotas.

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

A continuidade local acrescenta exclusão administrativa com prévia e tombstones externos, reaplicação após restauração, expiração de backups locais e cotas por conta. Procedimentos e limites em [EXCLUSAO_RETENCAO](docs/EXCLUSAO_RETENCAO.md). O roteiro para computador/celular/tablet está em [TESTES_DISPOSITIVOS](docs/TESTES_DISPOSITIVOS.md). Essas alterações estão na branch `feat/usability-feedback`; não houve deploy público.

## Cadastro e reutilização

Cliente é cadastrado durante o novo orçamento; fornecedor durante a nova compra. Para reutilizar, busque por nome, contato ou ID e selecione um resultado na própria página. “Pesquisar clientes/fornecedores” abre a consulta com ID e histórico associado. IDs são gerados automaticamente e os cadastros permanecem separados por conta.

“Biblioteca de peças” guarda a ficha reutilizável (materiais, tempo e preço) e mostra os pedidos relacionados. Para publicar um orçamento, primeiro adicione uma peça; o fluxo vazio orienta cadastrar a primeira ficha e voltar ao orçamento. Publicar gera o documento/link do orçamento para o cliente; não faz deploy da aplicação.

Um orçamento aprovado pelo link do cliente aparece na seção **Orçamentos aprovados** de **Pedidos e produção**: clique em **Criar / abrir pedido** para iniciar a produção. Em **Recebimentos e caixa**, essa seção permite registrar dinheiro já recebido; o valor aprovado não entra automaticamente no caixa. As listas mostram até 20 aprovações recentes e têm acesso a todos os orçamentos.

### Concluir uma encomenda sem repetir formulários

No pedido, clique em **Conferir e finalizar encomenda**. A tela sugere a produção total, o restante a entregar, o saldo a receber, a data de hoje e o último meio de pagamento do pedido (Pix quando ainda não há recebimentos). Confira e confirme ou edite antes de salvar. Para entregar depois, informe zero em **Entregar agora**; para produção parcial, desmarque **Concluir a produção**. Somente marque **Confirmo que recebi o valor abaixo** se o dinheiro já foi recebido. Sem essa confirmação, nenhum pagamento é registrado. Registre os consumos reais e pause o cronômetro antes de concluir; a revisão não inventa consumo ou tempo de trabalho.

O botão de recebimento separado também sugere saldo, data e meio de pagamento. Uma revisão desatualizada é bloqueada para evitar sobrescrever alterações de outra aba; um reenvio idêntico não duplica entrega nem recebimento.

### Adicionar peças direto no orçamento

Não é necessário cadastrar um projeto antes. Em **Adicionar peça**, deixe a biblioteca sem seleção e informe nome, quantidade e preço total. A peça e o item são salvos juntos, e a peça fica na biblioteca para reutilização. A ficha de materiais e tempo pode ser completada depois; enquanto os custos não forem conhecidos, a publicação exige reconhecer essa limitação.

Ao escolher uma peça da biblioteca, descrição e preço são preenchidos automaticamente. O preço sugerido acompanha a quantidade e os descontos da ficha; para fichas incompletas, usa o último preço manual proporcional à quantidade, quando disponível. Você pode editar os dados. Alterar a quantidade preserva um preço que você tenha editado manualmente. Descontos são opcionais; preço manual representa o total final e substitui o cálculo automático.

### Navegar pelas etapas do orçamento

As quatro etapas são links presentes no orçamento, nas condições, na inclusão/edição de peças, na revisão e no compartilhamento. Você pode voltar ou avançar para conferir informações. Salve suas alterações antes de trocar de etapa. Se faltar uma peça ou a publicação, a etapa seguinte explica como continuar. Em uma versão publicada, as condições e a revisão ficam disponíveis para leitura; alterações comerciais exigem nova versão. Navegar não publica, aprova, cria pedido ou registra recebimento.
