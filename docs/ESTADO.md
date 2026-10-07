# Estado para continuidade

Primeira entrega, 07/10/2026. Repositório inicialmente vazio, sem commits.
Usuário pediu início do desenvolvimento com preferência por Python. Implementação
autorizada pelo pedido atual; nenhuma autorização de deploy/publicação/cobrança.

Leia README, ARQUITETURA, REGRAS, ROADMAP e o código antes de continuar. Não recrie
o projeto. Preserve banco `.local/`, alterações e migrations existentes. Use checkout
atual; tarefas cloud já são isoladas, não criar worktree sem pedido explícito.

Concluído nesta fatia: Django, usuário UUID/e-mail único, sessões/cadastro/reset local,
owner de materiais pela sessão, entrada inicial atômica/idempotente, busca/paginação,
calculadora Decimal, telas pt-BR responsivas e testes. O texto fonte completo do PDF
foi salvo para rastreabilidade; instruções internas são propostas de referência.

Próximo passo recomendado: completar fundação (PostgreSQL, CI, backup/restauração,
rate limiting e configuração de e-mail) e então camadas/conversões/estoque. Não alegar
fase concluída inteira, produto pronto ou T01–T26 aprovados. Consulte VALIDACAO.
