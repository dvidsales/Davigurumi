# Ledger e observabilidade

## Decisão de segurança

Não foi implementado cache de ausência de tombstone, cache de bucket privado ou
réplica local. A leitura continua verificando o bucket e o objeto remoto em cada
chamada, validando a assinatura com chave separada e falhando de forma fechada.
Não há nova janela de revogação introduzida por cache. Cada worker verifica a fonte
independente do banco; restaurar usuário/sessão antigos não elimina o tombstone.

A auditoria identifica corretamente dois round trips potenciais por verificação.
O ambiente desta implementação não tem credenciais Supabase configuradas para
medir latência real e não foi autorizado alterar produção. Testes usam provedor
em memória e não demonstram a latência nem a política efetiva do bucket publicado.

Antes de adotar réplica/cache, seria necessário demonstrar uma autoridade externa
consistente, protocolo de invalidação em todos os workers, vínculo a uma geração
não restaurável com o banco e comportamento seguro diante de partição de rede.
Um TTL negativo arbitrário não satisfaz essa garantia. Esse desenho e os custos
operacionais adicionais permanecem pendentes, sem otimização declarada concluída.

## Instrumentação entregue

`DJANGO_PERFORMANCE_LOGGING=1` habilita `config.performance.PerformanceMiddleware`.
O padrão é desligado. Nenhuma variável foi alterada no Render.

Uma linha por resposta contém somente nome da rota resolvida, status, duração
total, quantidade/duração das execuções SQL, operações HTTP do storage e leituras
do ledger. Não contém caminho real, query string, SQL, parâmetros, IDs, cookies,
corpo, assinatura, URL do Supabase ou credenciais. Não habilita logging SQL.

`db_ms` mede execução de SQL, não estabelecimento da conexão; `remote_ms` inclui
leituras e checagens remotas. `ledger_ms` contém as chamadas HTTP do ledger, portanto
não deve ser somado a `remote_ms` como se fossem custos independentes. O total inclui
as camadas abaixo do middleware. Respostas servidas por WhiteNoise ou redirecionadas
pelo SecurityMiddleware antes dele não são medidas. Conexão fria/TLS devem ser
medidos separadamente. A implementação atual é síncrona WSGI e usa a conexão default.

As métricas usam ContextVar e são removidas ao terminar a requisição, inclusive
em erro. Não guardam resultado de autorização ou exclusão para outra requisição.
Os testes verificam propagação de falhas, ausência de conteúdo sensível nos logs,
tombstone após resposta negativa, usuário restaurado, assinatura inválida,
indisponibilidade e mudança de privacidade do bucket.

## Conexões PostgreSQL

`POSTGRES_CONN_MAX_AGE`: inteiro entre 0 e 300 segundos; padrão 0 conserva a política
anterior. `CONN_HEALTH_CHECKS=True` protege a reutilização de conexões. Testes locais
com 60 segundos exercitam a configuração; não homologam o pooler remoto.

Não ativamos pool cliente nem alteramos porta, search_path, SSL ou quantidade de
workers. Antes de habilitar persistência no beta, confirmar Session pooler (5432),
limite de conexões e schema privado. Não aplicar a recomendação ao Transaction
pooler sem revisar pressupostos de sessão. Com um processo e duas threads WSGI,
reservar até duas conexões persistentes por processo, além das conexões de deploy,
migração e processos sobrepostos durante substituição. Não configurar ilimitado.
