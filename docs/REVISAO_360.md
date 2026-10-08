# Revisão para testes privados — 08/10/2026

Escopo: fluxos de estoque, compras, precificação, peças, orçamento/publicação/aceite, pedidos, produção/entrega, pagamentos, exportação/restauração e privacidade; verificações automatizadas, revisão de código e navegação no Chromium. Nenhuma exclusão foi feita em dados reais.

## Problemas corrigidos

- Sugestão de preço com desconto fixo acima do preço causava erro 500. Agora retorna validação 400.
- Preço preenchido automaticamente acabava salvo como preço manual, congelando o valor ao alterar quantidades depois. Agora a sugestão permanece calculada no servidor; edição manual explícita continua disponível.
- Conclusão de produção podia validar campos de pagamento mesmo sem confirmar recebimento. Agora ignora esses campos quando o recebimento não foi marcado.
- Falha ao abrir uma imagem privada causava erro 500. Agora informa indisponibilidade 503 sem expor detalhes do armazenamento.
- Recuperação de senha com backend sem envio simulava sucesso. Agora orienta contatar o responsável, sem prometer e-mail.

## Preparação do beta

Gunicorn e WhiteNoise substituem o servidor de desenvolvimento no deploy. HTTPS, cookies seguros, CSRF, validação de host, limites de uso, autenticação e autorização permanecem ativos. O endereço do cliente usado no limite de tentativas vem do proxy somente quando explicitamente confiável. Cadastro exige convite criptográfico por e-mail e lista de até 20 participantes.

PostgreSQL usa TLS e usuário restrito em schema separado, sem acesso das funções públicas da API Supabase. Imagens e registros de exclusão usam buckets privados distintos. O backend não gera URLs públicas para imagens. Registros de exclusão mantêm assinatura com chave independente e sobrevivem a redeploys. Indisponibilidade do ledger bloqueia acesso, em vez de ignorar contas excluídas.

Verificações de inicialização recusam permissões inadequadas, buckets públicos, cadastro aberto, modo DEBUG e configuração incompleta. O endpoint de saúde revela somente disponibilidade.

## Limites da revisão

Testes automatizados cobrem regressões e isolamento; não substituem teste em dispositivos reais ou auditoria independente. Render/Supabase não foram provisionados: não há contas nem credenciais neste ambiente. Respostas do armazenamento remoto foram simuladas, incluindo indisponibilidade e bucket público. A rede bloqueou acesso à documentação/preços desses provedores. Não houve alteração de planos ou gasto.

Consulte [DEPLOY_TESTES_GRATUITO.md](DEPLOY_TESTES_GRATUITO.md) para ativar o beta e confirmar o armazenamento após reinício. Uso público permanece pendente de avaliação operacional, recuperação/backups, e-mail, retenção e revisão final de segurança.


## Evidência final

186 testes passaram no PostgreSQL; SQLite passou 181 e ignorou 5 exclusivos do PostgreSQL. Chromium cobriu a jornada completa e 31 telas, sem erros JS/5xx ou overflow nas larguras verificadas; axe não detectou violações. A auditoria das dependências não encontrou vulnerabilidades conhecidas; Bandit não encontrou problemas médios/altos. Gunicorn e migrations em schema privado com usuário restrito foram validados localmente. Detalhes e limites em [VALIDACAO.md](VALIDACAO.md).
