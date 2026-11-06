# Teste de carga automatizado no ambiente separado

O responsável criou `https://davigurumi-carga.onrender.com` e um Supabase exclusivo.
As capturas confirmaram `/healthz/` ok e versão `ee99ddc01be1`. Isso é uma observação
anterior do usuário, não uma nova medição de latência. O beta das participantes
permanece fora dos destinos permitidos pelo runner.

## Operação sem teste manual

O workflow **Teste de carga isolado**, em `.github/workflows/load-test.yml`, executa
preparo, autenticação, amostragem, parada automática e relatório. O operador não
precisa clicar em telas durante a medição, executar comandos ou ficar acompanhando.
É necessária uma configuração inicial de acesso: duas credenciais da conta fictícia
no novo ambiente. O agente não tem essas credenciais; acesso ao GitHub não permite
ler as senhas do aplicativo ou os valores de Actions secrets.

No GitHub, repositório → Settings → Secrets and variables → Actions → New repository
secret. Criar:

| Nome | Conteúdo |
| --- | --- |
| `DAVIGURUMI_LOAD_USERNAME` | Usuário da conta de testes de `davigurumi-carga`, não o e-mail, usuário do banco ou do GitHub. |
| `DAVIGURUMI_LOAD_PASSWORD` | Senha dessa conta no aplicativo; não usar chave do Supabase, senha administrativa ou segredo de convite. |

Nunca colocar valores em issues, PRs, arquivos, prints ou chat. Recomenda-se uma
conta dedicada somente a dados fictícios. O workflow não abre cadastro público,
não concede privilégios e não altera credenciais ou limites do servidor.

Depois dessa configuração, o agente pode acionar o workflow e analisar os artefatos:

```bash
gh workflow run load-test.yml --ref main
```

Disparos são serializados pelo GitHub; não iniciar outra carga por fora. O gatilho
manual pertence à automação: o usuário pode pedir ao agente que o acione.
Sem os dois secrets o workflow para antes de acessar o site.

Agenda semanal é opcional e **desabilitada por padrão**. Somente se a variável
`LOAD_TEST_WEEKLY_ENABLED` do repositório for `true`, roda às sextas às 19h UTC
(16h em Brasília). Não há keep-alive, execução contínua ou carga diária implícita.
Os limites atuais dos planos gratuitos devem ser acompanhados nos provedores;
a automação não compra capacidade nem garante disponibilidade.

## Preparo fictício e fases

Na primeira execução concluída, cria pela interface e seus serviços normais:

- Cinco materiais com estoque inicial fictício, mais um marcador de preparo.
- Duas peças/orçamentos aprovados pelo portal, convertidos em pedidos.
- Dez sessões de trabalho encerradas, sem sobreposição por proprietário.
- Planejamento de produção e dois recebimentos fictícios de R$10.

Não chama gateway de pagamento e não envia convites/e-mails. Não elimina registros.
O marcador `AUTOCARGA-v1-finalizado` permite reutilizar a fixture na execução seguinte.
Se o preparo for interrompido antes do marcador, podem permanecer dados parciais;
não há promessa de rollback HTTP transacional nem limpeza automática. O relatório
identifica a etapa da interrupção. Não reutilizar a conta para dados pessoais.

As amostras repetidas são GETs em oito rotas: início, materiais, orçamentos,
pedidos, calendário, relatório geral, financeiro e detalhe de pedido.

| Fase | Sessões autenticadas | Amostras por rota | Taxa global máxima de início |
| --- | --- | --- | --- |
| Baseline aquecida | 1 | 30 | 0,5 requisição/s |
| Exploração | 3 | 6 | 1 requisição/s |
| Exploração | 5 | 6 | 1,5 requisição/s |

São 336 amostras planejadas, além de login, checagem, aquecimento e preparo.
Não confundir cinco sessões com cinco proprietários distintos ou garantia de cinco
requisições simultâneas: `max_inflight` registra a concorrência efetiva. A taxa é
compartilhada entre workers, não multiplicada pela quantidade de sessões.

## Guardas

- Somente o host HTTPS exato `davigurumi-carga.onrender.com` é aceito remotamente.
  URL com credencial, outro host/porta/caminho ou beta original é recusada.
- Exige `DAVIGURUMI_LOAD_ISOLATED=1`. Modo local de integração só aceita HTTP loopback.
- TLS validado. Cookies/CSRF do Django são usados; credenciais não são repetidas
  em caso de falha. Não há bypass de convite, ledger, rate limit ou autorização.
- Para imediatamente diante de 401/403/429 ou redirecionamento inesperado durante
  a carga. Para com três erros consecutivos, mais de 10% de erros em janela com
  pelo menos dez respostas ou três respostas consecutivas acima de dez segundos.
- Timeout normal 15s; primeira checagem de saúde admite até 75s, sem fingir que a
  instância estava dormindo. Orçamento nominal de execução de 20 minutos e limite
  do job de 25 minutos, permitindo concluir/limpar requisições em andamento.
- Máximo de 450 requisições HTTP do runner e 600 recursos do navegador de preparo.
  Esses limites incluem requisições auxiliares e não são a meta de amostras.
- Redirecionamentos do cliente HTTP não podem sair da origem. Navegação de preparo
  também restringe recursos à origem e bloqueia service workers nesse contexto.
- Relatórios ficam sete dias em artefatos. Não contêm senha, usuário, e-mail,
  cookies, corpos HTML, tokens de portal ou URLs de objetos/IDs privados.

## Relatório e interpretação

`report.md` aparece no resumo da execução; `report.json` e Markdown são baixados
no artefato `davigurumi-load-report`. Há p50/mediana, p95 por rota e fase, contagem
de erros/status, bytes de resposta, concorrência real, versão publicada e duração
da primeira chamada. p95 usa nearest rank; seis amostras são somente exploratórias.

Mede resposta HTTP completa percebida pelo runner (inclui rede, TLS, fila e ponte
Playwright). Não mede LCP/INP/CLS ou tempo puro de servidor. Preparo tem tempos
separados, que incluem navegador e não são amostras de carga. Respostas HTTP acima
de p95 2,5s são destacadas como alerta exploratório, não como capacidade certificada.

Para separar banco, ledger remoto e aplicação, correlacionar com os logs agregados
já habilitados por `DJANGO_PERFORMANCE_LOGGING=1` no Render de carga. Este workflow
não possui chave da API do Render, portanto **não lê esses logs automaticamente**.
Não atribuir uma demora ao plano Free somente pelo p95 de rede. Medir um cold start
comprovado exige evidência de inatividade; o teste não força suspensão/restart.

A carga usa dados pequenos e leituras. O preparo valida escritas comerciais e
financeiras, mas não é teste concorrente de compras, consumo, entregas ou reembolsos,
nem benchmark com milhares de registros. Esses cenários são extensões futuras.

## Verificação local / CI

`node --test scripts/load/core.test.cjs` verifica destino, redirecionamento,
percentis, taxa global e circuito de parada. `--local-smoke` executa a fixture real
e três fases curtas (24 amostras) contra PostgreSQL descartável, nunca o beta.
A CI padrão executa esse smoke local em banco separado e sem Actions secrets reais.
Resultados locais comprovam funcionamento do runner, não desempenho do Render.

O ambiente cloud atual não tem credenciais da conta nem acesso de rede ativo ao
novo host. Foi salvo um rascunho aditivo de rede com `davigurumi-carga.onrender.com`,
preservando `api.github.com`; ele exige revisão/salvamento/publicação nas configurações
do ambiente para acesso direto daqui. Isso não configura credenciais nem comprova
execução remota. O workflow roda em GitHub Actions, independentemente desse acesso
direto do workspace.

Não foi necessário modificar código funcional, banco ou configurações do Render
para instalar o runner. Não é necessário novo deploy do aplicativo para executá-lo.

### Evidência desta implementação (06/11/2026)

- Sete testes Node de segurança/estatística passaram.
- Preparo local completo criou os exemplos e terminou 16 leituras no primeiro smoke.
- Reexecução com as três fases curtas terminou 24 leituras sem erros; fixture reutilizada,
  sem acrescentar registros. Contagens: seis materiais, duas peças, dois orçamentos,
  dois pedidos, dez sessões e dois pagamentos.
- Evidência sintética em `evidencias/carga-automatica/integracao-local.json`.
- Nesta medição local as respostas foram rápidas e `max_inflight=1`, mesmo com cinco
  sessões configuradas. Não apresentamos isso como cinco acessos simultâneos reais.
- O teste remoto ainda depende dos dois Actions secrets. Nenhum teste de carga foi
  executado no Render durante a implementação; não há percentis remotos a reportar.
