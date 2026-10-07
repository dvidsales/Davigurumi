# Registro de decisões

Data: 07/10/2026. A origem das escolhas é explícita; recomendações não equivalem a
aprovações do usuário.

| ID | Questão / alternativas | Escolha e motivo | Estado / origem / impacto |
| --- | --- | --- | --- |
| D01 | Linguagem: Python ou TypeScript | Priorizar Python | Preferência explícita do usuário; backend/framework Python |
| D02 | Django, FastAPI/React, React/Supabase | Django modular + templates | Decisão técnica desta primeira entrega, pela manutenção simples; PostgreSQL futuro |
| D03 | Banco local PostgreSQL ou SQLite | SQLite para desenvolvimento inicial, PostgreSQL antes de concorrência | Escolha técnica temporária; não comprova transações/locks de produção |
| D04 | Direção visual | Verde profundo e sálvia provisórios; alternativas azul/areia documentadas | Não aprovada como identidade final; tokens CSS substituíveis |
| D05 | Referência/alocação/valorização | Média disponível/FIFO físico/custo específico | Proposta do PDF, ainda não implementada; ratificar antes de camadas/custos |
| D06 | Consumo | Explícito e parcial; início de produção não baixa estoque | Contrato de referência preservado; módulo ainda não implementado |
| D07 | Versões/aceites | Uma versão vigente, pedido único por aceite, aditivo | Proposta do PDF; pendente antes do comercial |
| D08 | Dinheiro | Decimal, half-up, fórmulas §59 | Implementado em simulação, sem cobrança/transação comercial |
| D09 | Cronômetro | Uma sessão ativa por pessoa | Proposta; ratificar trabalho simultâneo antes da produção |
| D10 | Gratuidade | R$ 0 local; não ativar serviços pagos | Local verificado; hospedagem pública/SMTP/backup não escolhidos |
| D11 | Recuperação | Console Django no desenvolvimento | Funciona tecnicamente; não é envio de e-mail real |
| D12 | Privacidade/backup | Sem dados reais no piloto até controles operacionais | Não há backup diário/destino independente ou política legal final |

Configurações sugeridas para módulos futuros (não preferências informadas): validade
de orçamento 15 dias; fuso America/Sao_Paulo; uploads de 5 MB; alerta a 70% de cota.
Só o fuso está efetivamente configurado na aplicação atual. Não há módulo de orçamento/upload.

Pendências que não impedem o desenvolvimento local: hospedagem Python sem cobrança,
SMTP para notificações/recuperação, destino independente de backup, identidade final,
política de valorização e retenção. Nenhum segredo foi solicitado em chat ou incluído
no repositório. Essas decisões serão necessárias antes dos respectivos recursos/piloto.
