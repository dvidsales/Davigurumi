# Continuidade

A autorização atual permite continuar o desenvolvimento sem aguardar teste manual. A referência de produto não autoriza deploy/serviços pagos. Os módulos funcionais estão descritos no README; as pendências abaixo não devem desaparecer do escopo.

## Próximos itens de implementação

- Arquivamento de materiais e atributos técnicos adicionais por categoria; composição, espessura, agulha recomendada e estoque mínimo disponível já estão implementados.
- Devoluções/retificações de recebimento com vínculos compensatórios e reversão de consumo no fluxo do pedido.
- Conciliação de aditivo com remoção de item ou alteração de materiais já comprometidos; hoje operações inseguras são rejeitadas.
- Duração padrão, planejamento/calendário, seleção da política de referência por ficha e custos adicionais efetivos; indicadores de lucro precisam dessa completude.
- Relatórios detalhados por material e visualização de diferenças entre versões; pedidos já têm filtros por cliente/projeto/produção e exportação CSV/XLSX.
- Importação/exportação de templates adicionais; pacote completo tem limite 10000 registros/50 MB, assinatura ligada à chave original e não faz merge entre bases existentes.
- Push Web Push com explicação/opt-in, assinatura e entrega efetiva; validação da PWA em Safari/Android, instalação e permissões em dispositivos reais.
- Eliminação/anonimização, retenção por categoria e tombstones com testes de restauração, após política definida. Revisão técnica em PRIVACIDADE.
- Automatizar evidências restantes T01–T26, testes de uploads grandes, cargas/cotas e acessibilidade com leitor de tela. Testes locais não equivalem a homologação do usuário.

## Dependências operacionais

Hospedagem Python/HTTPS, SMTP/remetente, agendador para alertas/outbox, backup diário em destino independente e política de retenção. Definir limites de uso comercial e cotas dos planos gratuitos antes de escolha. O app não processa dinheiro nem integra banco.

## Git

Continuar com branches de funcionalidade e PRs. Manter `main` como versão revisada e utilizável, protegida por checks e revisão. `develop` só se justificar por integração de várias funcionalidades/releases em paralelo; não é necessária neste início. Não criar/alterar proteção de branch ou fazer merge sem autorização correspondente.
