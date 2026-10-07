# Plano e rastreabilidade

Todo o MVP original foi mantido. A primeira entrega é uma fatia de desenvolvimento,
não conclusão das fases 0–4, nem autorização para lançamento.

| Fase do PDF | Entrega restante / situação | Evidências a exigir |
| --- | --- | --- |
| 0 Arquitetura | Alternativas/stack/modelo registrados; infra pública/decisões propostas pendentes | Quotas/termos atuais, SMTP, destino backup, direção visual |
| 1 Fundação | Contas, auth local, migrations, proteção CSRF e testes feitos; faltam hardening, CI, backup operacional, SMTP, PWA | T01 inicial, recuperação SMTP e restauração real |
| 2 Materiais/estoque | Cadastro e abertura feitos; faltam atributos completos, conversões, camadas, ajustes, reserva e reconciliação | T02–T04, T26 |
| 3 Compras/custos | Não implementada | T05–T07, T25 |
| 4 Projetos/preço | Fórmulas em calculadora testadas; ficha, revisões, snapshots, preço manual e rateios pendentes | T08 integrado e casos-limite |
| 5 Clientes/orçamentos | Não implementada | T09, PDF/projeção pública |
| 6 Portal/aceite | Não implementada | T10–T12, concorrência terminal |
| 7 Pedidos/produção | Não implementada | T13, T16, entrega parcial |
| 8 Financeiro/mensagens | Não implementada | T14, T15, T20 |
| 9 Dashboard/relatórios | Apenas resumo real do acervo; demais indicadores pendentes | Conciliação sem dupla contagem |
| 10 Portabilidade/demo | Não implementada | T17, T18, T21–T23 |
| 11 Qualidade/piloto | Não iniciada | T01–T26, fluxo §52 e critérios §76 |

## Matriz completa por grupos do PRD

| Seções | Requisitos | Estado / fase |
| --- | --- | --- |
| 1–5 | Produto genérico, pessoas individuais, isolamento | Direção preservada; isolamento atual testado; evoluir em todas as fases |
| 6–10, 54 | Tipos, fios/tex, cores, unidades, cadastro progressivo | Parcial: campos base; sem conversões/atributos avançados; fase 2 |
| 11–17, 55–58 | Compras, fornecedor, repetição, lote, custos, ledger, reservas | Somente abertura e custo desconhecido; fases 2–3 |
| 18–21, 59–60 | Projetos, ficha/alternativas, mão de obra, preços, múltiplos itens | Calculadora isolada; restante fase 4 |
| 22, 29, 63–64 | Pedido, produção, tempo, entrega | Pendente fase 7 |
| 23–28, 61–62 | Clientes, versões, imagens, PDF, portal, aceite | Pendente fases 5–6 |
| 30–31, 65, 67 | Parcelas, pagamentos, estornos, notificações/outbox | Pendente fase 8 |
| 32–34, 66 | Dashboard, relatórios, pesquisa/filtros | Busca de materiais e resumo parcial; fase 9 completa |
| 35–40, 68–69 | Import/export, backup, arquivamento, onboarding/demo | Pendente fase 10; backup mínimo antecipado na fundação |
| 41–45, 72 | Identidade, mobile/PWA, acessibilidade, idioma, erros | pt-BR/responsivo/foco/labels iniciais; PWA e auditoria AA pendentes |
| 46, 53, 70–71 | Privacidade, vínculos, retenção, auth/segurança | Auth local/owner atual; hardening/retention/vínculos futuros pendentes |
| 47–50, 73–74 | Arquitetura, processo, autonomia, histórico, operação | Plano e decisões; produção/backup/custos ainda não validados |
| 51–52, 75–76 | Escopo, jornada completa, T01–T26, lançamento | Critérios preservados; produto ainda não é MVP pronto |

## Próxima entrega recomendada

Completar a fundação: PostgreSQL de desenvolvimento e testes, backup/restauração
automatizados, CI, limitação de tentativas e canal de recuperação configurável.
Depois evoluir materiais para camadas, conversões e movimentos com reserva/consumo
concorrentes, usando pedidos sintéticos antes da interface comercial.

Cada fase exige implementação, testes e revisão. Não existe estimativa de prazo confiável
antes de observar velocidade e fechar infraestrutura. Faixas relativas de esforço:
fundação médio; estoque e compras alto; ficha/preço médio-alto; comercial/portal alto;
produção/financeiro alto; relatórios médio; portabilidade/recuperação alto; revisão final
alto. Reestimar após compras com base em entregas efetivas.

Pós-MVP: relatórios/dashboard avançados, sugestões históricas/inteligentes, offline
avançado e automações adicionais. Futuro: equipes/ateliês, colaboração, WhatsApp,
código de barras e IA. Nenhum desses substitui módulos obrigatórios do MVP.
