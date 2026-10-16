# Relatórios e notificações

O primeiro ajuste mobile deixou os formulários de movimentos/calendário com `form.as_p` dentro de cartões que não recebiam os estilos dos campos. Agora os dois usam campos compartilhados com labels, bordas, altura e erros consistentes.

## Notificações

O sino fica no cabeçalho do celular e no topo da barra lateral, fora de Mais. Mostra um contador de não lidas, limitado visualmente a 99+; o nome acessível informa a quantidade real. Ao ler uma notificação e carregar a página seguinte, o contador é atualizado. A consulta é restrita ao proprietário autenticado, incluindo o espaço de demonstração; visitantes não consultam notificações. Não há polling ou mudança nas preferências de envio.

No desktop, o conteúdo do menu tem rolagem própria para preservar o sino e a área da conta visíveis.

## Movimentos por material

Datas e material são apresentados em grid adaptável. A consulta e a limpeza ficam juntas; exportações CSV/XLSX têm grupo próprio. Sem registros, a tela orienta ajustar os filtros em vez de apresentar uma tabela vazia. Filtros inválidos mostram os erros e não afirmam que não existem movimentos. O custo histórico e a ressalva sobre pagamentos/lucro continuam descritos.

## Calendário

O período fica visível; produção, cliente e peça estão em filtros adicionais expansíveis, abertos quando selecionados ou inválidos. Compromissos são agrupados por dia, com tipo, situação e tempos. Pedidos sem planejamento ficam em um painel separado. Tamanhos, espaçamento e textos refluem no celular.

Consultas, filtros, exportações, paginação e regras de produção mantêm os serviços existentes. Não há migrations, dependências novas ou alterações nas variáveis do Render.

## Evidência

- 190 testes aprovados no PostgreSQL; SQLite 185 aprovados e 5 exclusivos ignorados.
- Contador por proprietário, leitura, visitante sem consulta e estados de filtros inválidos cobertos por regressões.
- 112 verificações de layout (14 páginas, 320 a 1440 px), seis auditorias axe específicas e jornada completa de 31 telas aprovadas.
- Revisão de movimentos/calendário: sete auditorias axe em desktop/mobile, dados e erros; CSV baixado; contador reduzido após leitura.
- Os roteiros devem rodar sequencialmente em banco descartável; repetições intensivas podem acionar os limites de requisição. Nenhum limite da aplicação foi relaxado.
- As capturas usam dados fictícios. Safari e aparelhos reais continuam dependendo de conferência física, conforme [MOBILE.md](MOBILE.md).

## Capturas

- [Movimentos no computador](images/reports-movimentos.png)
- [Calendário no computador](images/reports-calendario.png)
- [Movimentos no celular](images/reports-movimentos-mobile.png)
- [Calendário no celular](images/reports-calendario-mobile.png)

Depois de integrar o PR, use **Manual Deploy → Deploy latest commit** no serviço Render. Não é necessário editar variáveis ou sincronizar o Blueprint.
