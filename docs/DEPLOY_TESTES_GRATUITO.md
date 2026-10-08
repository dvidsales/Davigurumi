# Testes com outras pessoas, sem orçamento

A configuração deste repositório usa um serviço **Free do Render** e um projeto **Free do Supabase** para PostgreSQL e arquivos privados. Não precisa comprar domínio: use o endereço `https://SEU-SERVICO.onrender.com`. A aplicação fica acessível pela internet, mas o cadastro exige convite individual; isso não equivale a uma rede privada. Use dados fictícios nesta fase.

Os planos gratuitos têm limites, podem suspender por inatividade e não garantem disponibilidade. Confirme que ambos os painéis mostram **Free / US$ 0** antes de criar recursos. Não selecione upgrades, discos pagos ou um banco Render. Nesta revisão, o acesso às páginas dos provedores foi bloqueado pela rede do ambiente; os limites e a disponibilidade atuais não foram confirmados ao vivo. Consulte [Render](https://render.com/docs/free) e [Supabase](https://supabase.com/pricing). Nenhuma conta ou recurso externo foi criado automaticamente.

## 1. Criar o projeto Supabase

1. Crie sua conta e um projeto Free no Supabase. Guarde a senha do banco em um gerenciador de senhas.
2. Em **Connect**, copie os parâmetros do **Session pooler**, porta **5432**. Não use o Transaction pooler da porta 6543. O Session pooler permite conexão IPv4 e mantém o contexto de sessão necessário ao Django.
3. Em **Storage**, crie dois buckets, ambos com **Public bucket desativado**: `davigurumi-files` e `davigurumi-erasure`. Não crie políticas públicas de leitura ou escrita. O segundo guarda registros assinados de exclusão; não deve ser apagado ao restaurar um backup antigo.
4. Em configurações/API, copie a URL do projeto e a chave legada **service_role**. Essa chave tem privilégios elevados: somente o servidor a recebe. Nunca coloque em JavaScript, screenshots, GitHub ou mensagens. Este backend usa a chave JWT legada `service_role`.
5. Prepare um usuário exclusivo do banco, com acesso apenas ao schema privado `davigurumi`. No terminal do VS Code, com a `.venv` ativada e as dependências instaladas:

   ```bash
   python scripts/setup_supabase_database.py
   ```

   O script pede host e usuário administrativo do Session pooler (normalmente `postgres.REFERENCIA_DO_PROJETO`), a senha administrativa e uma **nova senha de pelo menos 24 caracteres** para a aplicação. As senhas são ocultadas e não ficam em arquivos. Ele cria o papel `davigurumi`, sem privilégios de superusuário, e um schema de mesmo nome, sem acesso para `anon`, `authenticated` ou `PUBLIC`. Se esse papel já existir, interrompe sem sobrescrever. Não execute contra uma instalação já em uso.
6. A conexão usada pelo Render será `davigurumi.REFERENCIA_DO_PROJETO`, com a nova senha. O banco continua sendo `postgres`. **Não adicione o schema `davigurumi` aos schemas expostos pela Data API**. Não use o usuário administrativo no aplicativo.

As conexões exigem TLS com validação de certificado (`verify-full`). Se houver erro de CA, obtenha o certificado oficial do provedor e configure `POSTGRES_SSLROOTCERT` para o arquivo correspondente; não desative a verificação. O padrão `system` utiliza as autoridades confiáveis do sistema.

## 2. Criar o serviço Render

1. Crie uma conta Render e conecte o repositório GitHub. A atualização precisa estar na branch que você selecionar para deploy.
2. Escolha **New → Blueprint**, selecione o repositório e confira o `render.yaml`. Ele cria **somente um Web Service Free**, sem banco ou disco Render. O deploy automático está desativado.
3. Preencha as variáveis solicitadas. Se o endereço do serviço ainda não estiver disponível, termine a criação sem considerar o primeiro deploy aprovado, copie o domínio atribuído e atualize as variáveis antes de realizar o deploy novamente.

| Variável | Valor |
| --- | --- |
| `POSTGRES_HOST` | Host do Session pooler do Supabase |
| `POSTGRES_USER` | `davigurumi.REFERENCIA_DO_PROJETO` |
| `POSTGRES_PASSWORD` | Nova senha exclusiva da aplicação |
| `DJANGO_ALLOWED_HOSTS` | `SEU-SERVICO.onrender.com`, sem `https://` ou `*` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://SEU-SERVICO.onrender.com` |
| `DJANGO_BETA_EMAILS` | E-mails autorizados separados por vírgula, de 1 a 20 pessoas |
| `SUPABASE_URL` | `https://REFERENCIA.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Chave JWT `service_role`, somente no painel do servidor |

O Blueprint gera `DJANGO_SECRET_KEY`, `DJANGO_PRIVACY_LEDGER_KEY` e `DJANGO_BETA_INVITE_SECRET`. Confirme que a primeira tem pelo menos **50 caracteres** e as outras pelo menos **32**. Se necessário, gere valores locais com `python -c "import secrets; print(secrets.token_urlsafe(64))"` e salve no painel. **Guarde os três valores separadamente e mantenha-os estáveis nas atualizações.** A chave de exclusão deve ser diferente da chave Django. Perder/trocar a chave de exclusão impede validar os registros de contas apagadas.

As demais variáveis já estão no Blueprint. Não habilite `DEBUG`, cadastro aberto, armazenamento local ou `sslmode=disable`. `DJANGO_TRUST_PROXY=1` exige que o acesso à aplicação passe pelo proxy HTTPS confiável do Render, que deve substituir/acrescentar o endereço real como último IP de `X-Forwarded-For`; não exponha o processo Gunicorn diretamente em outro servidor.

O build instala dependências e gera CSS/JS comprimidos. A inicialização executa migrations, verificações Django e `check_beta --strict` antes de abrir o Gunicorn. A aplicação se recusa a iniciar se banco, convites, permissões do schema ou buckets privados não estiverem corretos. Consulte os logs sem copiar credenciais.

## 3. Convidar os participantes

1. Coloque o e-mail da pessoa em `DJANGO_BETA_EMAILS` e faça o redeploy para aplicar a lista.
2. Em seu computador, execute:

   ```bash
   python scripts/beta_invite.py pessoa@exemplo.com
   ```

3. Quando solicitado, cole o valor de `DJANGO_BETA_INVITE_SECRET` do painel. O script oculta o segredo e imprime **apenas o código daquela pessoa**. Não envie o segredo principal.
4. Envie manualmente à pessoa o endereço `https://SEU-SERVICO.onrender.com/conta/criar/` e o código individual. Ela cadastra o mesmo e-mail e escolhe sua própria senha. O código não autoriza outro e-mail.

Cada conta tem seus próprios dados. Os links de orçamento são acessíveis a quem possuir o link: compartilhe somente com quem participa daquele teste. Remover um e-mail da lista impede novos cadastros, mas **não suspende uma conta já criada**. Para suspender um participante, desative `is_active` pelo Django admin usando uma conta administrativa do responsável. Nunca entregue acesso administrativo aos convidados.

Nesta configuração inicial, não há serviço de envio de e-mail. Recuperação de senha informa essa limitação. O responsável pode executar `python manage.py changepassword NOME_DO_USUARIO` a partir de um computador com as variáveis do banco/configuração definidas com segurança. Não envie senhas por GitHub ou chat. Para recuperação automática, configure depois um backend SMTP e suas credenciais. Não use o backend de console em produção.

## 4. Conferir antes de convidar

- Abra `/healthz/`: deve retornar `{"status":"ok"}` por HTTPS.
- Abra o login: CSS e JavaScript precisam carregar; HTTP deve redirecionar para HTTPS.
- Tente cadastrar sem convite e com e-mail não autorizado: precisa recusar.
- Cadastre duas contas fictícias; confirme que uma não vê nem altera materiais, clientes, orçamentos e imagens da outra, inclusive ao copiar URLs.
- Percorra orçamento → link do cliente → aprovação → pedido → produção → entrega → recebimento. Confirme os totais antes de confirmar ações.
- Faça um redeploy e confira que registros e imagens continuam disponíveis: nenhum dado depende do disco temporário Render.
- Confirme nos painéis que ambos continuam no plano Free. Não ative upgrade para contornar limites; reduza a quantidade de testes.

## 5. Atualizações e backups

Use **Manual Deploy → Deploy latest commit** após revisar e integrar a atualização. Aguarde migrations e verificações. O Blueprint não publica novos commits automaticamente. A versão de Python está fixada; se o Render não oferecer essa versão, escolha uma versão 3.12 corrigida disponível e valide novamente.

Faça exportações de **pacote completo** por conta e guarde fora desses provedores, protegidas: contêm dados pessoais e imagens. A importação exige destino vazio e preserva IDs; não é sincronização entre duas contas da mesma instalação. Backups completos da instalação também precisam de `pg_dump` do schema privado, dos dois buckets e das chaves; não presuma backups automáticos do plano gratuito. Registros de exclusão mais recentes devem ser conservados separadamente e reaplicados após qualquer restauração, conforme [EXCLUSAO_RETENCAO.md](EXCLUSAO_RETENCAO.md).

O armazenamento remoto e a restauração foram testados com simulação do protocolo. A integração real Render/Supabase precisa ser conferida após criar suas contas: este ambiente não tem suas credenciais. A revisão não certifica ausência de vulnerabilidades nem libera uso público com dados reais.
