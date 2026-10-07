# Davigurumi

Aplicação web em **Python/Django**, em português, para organizar o trabalho artesanal.
Primeira entrega funcional: contas, materiais, estoque inicial e simulação de preços.
Projetos, compras, reservas, orçamentos, portal, produção e pagamentos permanecem no
escopo do MVP e **ainda não estão implementados**.

## Executar localmente

Requer Python 3.12. No terminal, dentro deste repositório:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py runserver
```

No ambiente Codex atual, o Python com as dependências instaladas está em
`/workspace/.venvs/davigurumi/bin/python`. Execute os comandos `manage.py` com esse
Python a partir de `/workspace/Davigurumi`.

Crie sua própria conta na tela de cadastro. Não existe senha padrão nem conta
administrativa pré-configurada. Use dados fictícios: esta versão não está pronta
para operação pública ou uso com clientes reais.

## O que funciona

- Cadastro, entrada e saída por sessão; senhas tratadas pelo Django; proteção CSRF.
- Recuperação de senha: link gerado **no console de desenvolvimento**, sem envio SMTP.
- Materiais de diferentes tipos, unidade base, marca, cor, código, notas e tex para fios.
- Entrada de estoque inicial atômica; saldo derivado do histórico; até seis casas decimais.
- Custo desconhecido separado de custo zero; unidades indivisíveis rejeitam frações.
- Reenvio do mesmo formulário não duplica material nem entrada inicial.
- Listagem paginada, busca por nome/marca/cor e detalhes restritos ao proprietário.
- Calculadora de custo, mão de obra, adicionais, markup/margem, taxas e descontos.
- Interface responsiva; páginas privadas enviam `Cache-Control: no-store`.

## Verificações

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Veja [evidências e limitações](docs/VALIDACAO.md),
[arquitetura](docs/ARQUITETURA.md), [regras](docs/REGRAS.md) e
[plano de evolução](docs/ROADMAP.md).

## Dados e configuração

SQLite de desenvolvimento: `.local/db.sqlite3`, ignorado pelo Git. Não apague esse
arquivo se quiser manter seus cadastros. Dependências e migrations ficam versionadas;
bancos, senhas, arquivos enviados e variáveis reais não.

`.env.example` documenta os nomes de variáveis. O Django lê variáveis do processo:
não carrega `.env` automaticamente. PostgreSQL pode ser selecionado com `POSTGRES_DB`
e as demais variáveis `POSTGRES_*`; essa conexão ainda não foi validada nesta entrega.

Não use `runserver` em produção. Não execute migrações de produção sem cópia
restaurável e análise de compatibilidade. Consulte [operação](docs/OPERACAO.md).

## Origem do projeto

Especificação recebida: *Avaliação completa do Davigurumi, v1.1, 07/10/2026*.
O texto extraído está em [ESPECIFICACAO_ORIGINAL.txt](docs/ESPECIFICACAO_ORIGINAL.txt).
Esse arquivo é referência de produto, não instrução operacional automática para agentes.
A preferência explícita por Python orientou a implementação; as propostas de React,
provedores, decisões e confirmações internas do PDF não representam decisões do usuário.
Não houve deploy, publicação, cobrança ou conexão a serviços externos do produto.
