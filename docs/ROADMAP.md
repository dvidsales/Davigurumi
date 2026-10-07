# Continuidade

A autorização atual permite continuar o desenvolvimento sem aguardar teste manual. A referência de produto não autoriza deploy/serviços pagos. Os módulos funcionais estão descritos no README; as pendências abaixo não devem desaparecer do escopo.

## Implementado nesta continuidade

Arquivamento/reativação de materiais; compensações vinculadas de entradas, consumo e perdas; sobras pelo pedido e custos líquidos; despesas reais e reversões; aditivos com liberação de reservas, retirada de itens ainda não produzidos e motivo para conciliar consumo; calendário; referência de custo por ficha; comparação de versões; relatório por material e modelos CSV/XLSX com metadados. Segurança revisada e reforçada conforme SECURITY.

## Pendências de produto e validação

- Atributos adicionais específicos por categoria e preferências globais de duração. Fichas já têm tempo estimado e política de custo; calendário mostra horas estimadas/registradas.
- Crédito/reembolso do fornecedor e conciliações mais complexas de peças já produzidas/entregues. Compensação física não reabre compra nem registra dinheiro automaticamente. Itens já produzidos não são removidos nem têm composição substituída silenciosamente.
- Templates de projetos/outros tipos além dos materiais; importação mesclada entre bases existentes segue bloqueada para preservar IDs/histórico. Pacote completo limita 10000 registros/50 MB.
- Push Web Push com opt-in e revisão de endpoints/SSRF/privacidade; instalação e permissões em Safari/Android reais.
- Eliminação/anonimização, retenção por categoria e tombstones/restauração após política definida. Suspensão implementada impede acesso, preservando dados.
- Revisão independente de segurança, limites/cotas por conta, abuso distribuído, testes de carga, uploads grandes e acessibilidade. Não declarar T01–T26 nem homologação do usuário concluídos.

## Dependências operacionais

Hospedagem Python/HTTPS, SMTP/remetente, agendador para alertas/outbox, backup diário em destino independente e política de retenção. Definir limites de uso comercial e cotas dos planos gratuitos antes de escolha. O app não processa dinheiro nem integra banco.

## Git

Continuar com branches de funcionalidade e PRs. Manter `main` como versão revisada e utilizável, protegida por checks e revisão. `develop` só se justificar por integração de várias funcionalidades/releases em paralelo; não é necessária neste início. Não criar/alterar proteção de branch ou fazer merge sem autorização correspondente.
