# Contratos de negócio implementados

Referência: PRD extraído, seções 53–76. Decisões técnicas abaixo implementam o protótipo e podem ser revistas com feedback; não representam aprovação legal ou comercial.

## Estoque e custo

Unidades base: g, m, un; `un` não aceita fração. Tex positivo só para fios. Massa e comprimento não são convertidos universalmente: apresentações específicas pertencem ao material e têm versão/fator preservado no movimento. A unidade base do cadastro não muda pela edição.

Custo `None` é desconhecido; zero é conhecido. Material sem quantidade inicial não recebe camada fictícia. Quantidades/custos por unidade têm seis decimais, máximo 999999,999999, validado também com SQLite.

Físico vem do ledger; reservado vem das reservas/camadas; disponível = físico − reservado. Reserva não baixa físico. Consumo de reserva baixa físico e reservado; liberação baixa apenas reservado. Consumo livre não usa saldo reservado. Escolha de camada é FIFO por criação/ID; custo realizado vem da camada efetivamente consumida. Estimativa pode usar custo mais antigo, recente ou média disponível; fichas usam média disponível e referência manual explícita quando necessária.

Alterar referência atual não reescreve custos históricos. Estoque negativo é rejeitado. Serviços transacionais usam lock do proprietário para serializar operações correlatas no PostgreSQL; a chave de operação é única por proprietário e o payload precisa ser igual numa repetição. PostgreSQL é necessário para a garantia concorrente; SQLite é conveniência local.

## Compras e fichas

Rascunho não movimenta estoque. Frete e desconto são rateados em centavos pelo maior resto, com desempate determinístico. O formulário permite rateio manual: o custo final de cada item inclui sua parte de frete/desconto, tem até duas casas decimais e a soma deve fechar exatamente o total da compra. Isso permite confirmar itens com preço zero e encargos. A confirmação preserva o método e os custos; repetir o mesmo rateio é idempotente e mudar valores já confirmados é rejeitado. Cada recebimento parcial cria suas próprias camadas. Cancelar o restante conserva recebimentos. Repetir compra cria rascunho novo e editável.

Ficha calcula para uma quantidade-base. Alterações criam revisão; alternativas são escolhidas por item de orçamento, sem substituição automática. Escalas que produzam fração de material indivisível são rejeitadas.

## Preço

`Decimal`, half-up em centavos, intermediários com precisão maior. `C = materiais + segundos/3600 × valor/hora + adicionais`. Markup `P0 = C × (1 + k)`. Margem `P0 = C/(1 − m − t)`. Desconto `P = P0 × (1 − d) − D`. No markup, taxas são deduzidas do resultado e não aumentam P0. Resultado `P × (1 − t) − C`; margem indefinida quando P=0. `m+t` precisa ser menor que 100%.

Custos desconhecidos deixam cálculo incompleto. Publicação exige preço manual e reconhecimento da limitação; preço abaixo do custo após taxas exige confirmação explícita. Não alegar lucro real com base em subtotais de consumo: custos adicionais efetivos e despesas externas ainda não são lançados.

## Comercial e cliente

Publicação congela itens, condições, validade, seleção de imagens, projeções pública/privada, hash e bytes do PDF. Campos internos/custos não entram no portal. Links aleatórios são armazenados apenas como hash; podem expirar ou ser revogados. Reemissão invalida links anteriores. GET não aprova; POST com CSRF e declaração explícita aceita a versão/hash exatos. Acesso por link não comprova identidade nem assinatura digital certificada.

Nova versão substitui versão não aceita; aceite existente continua preservado. Alteração após aceite gera aditivo que exige outro aceite. Aplicação ao pedido conserva consumo e pagamentos; redução abaixo do produzido/entregue e alterações de materiais já reservados/consumidos são rejeitadas para exigir conciliação. Remoção de itens já convertidos ainda não é conciliada automaticamente.

## Produção e caixa

Converter aceite em pedido é idempotente; não inicia nem consome. Produção, entrega e situação financeira são separados. Há uma sessão ativa por pessoa; fechar navegador não para o timer. Pausa calcula intervalo no servidor; correção mantém valor original e acrescenta motivo/duração. Entregas não excedem produzido.

Cancelar libera reservas remanescentes, conserva consumo e dinheiro, indica pendência de reembolso. Concluir exige quantidade produzida completa e sessão encerrada; não registra entrega nem quita financeiro. Reabrir exige motivo e não desfaz lançamentos.

Recebimentos são registros manuais, sem banco/gateway. Sinal anterior ao pedido é vinculado ao mesmo pagamento ao converter. Previsão não aumenta caixa; reversão não apaga recebimento. Reembolso não supera saldo recebido e excedente exige reconhecimento. Parcelas exibem distribuição do líquido por vencimento, sem gerar cobranças bancárias. Caixa por período usa data do pagamento e, separadamente, data de cada reembolso. Saldos dos pedidos no relatório são atuais.

## Portabilidade e demonstração

CSV/XLSX importam novos materiais, não atualizam silenciosamente cadastros. Prévia não movimenta estoque; qualquer erro impede confirmação inteira. Repetir confirmação não duplica. Texto numérico tem formato escolhido; números tipados de XLSX independem do formato textual. Fórmulas XLSX são rejeitadas; exportação neutraliza texto com aparência de fórmula.

Pacote relacional é autenticado pela chave do ambiente original, exige conta/base sem colisões e armazenamento vazio, inclui arquivos por hash e não inclui senhas/sessões. Não mescla bases. Links são revogados e aceites importados não autorizam novos pedidos, enquanto pedidos já existentes são preservados.

Demonstração usa proprietário separado, mantendo autenticação da conta real. Cópia requer senha e seleção; projetos trazem seus materiais, com estoque/custos/horas/preços zerados, sem pagamentos ou clientes fictícios.


## Estoque mínimo e relatórios

Composição, espessura e agulha recomendada são descrições opcionais; não alteram conversões ou custo. O mínimo é informado na unidade base e deve ser inteiro para materiais em unidades. Mínimo zero desativa o aviso. A visão geral e os relatórios comparam o mínimo com o estoque disponível, após reservas; alertas gerados pelo comando são deduplicados por material/dia e proprietário. Não há agendador automático embutido.

Cliente, projeto e estado de produção filtram os pedidos criados no período. O filtro de projeto consulta os itens da versão comercial atual, preservando uma linha por pedido mesmo quando há vários itens desse projeto. O caixa permanece global da conta por data efetiva de recebimento/reembolso. CSV e XLSX usam as mesmas linhas, neutralizam nomes com aparência de fórmula e mostram total/saldo/crédito atuais, não um saldo histórico reconstruído. XLSX inclui valores monetários numéricos com duas casas de exibição.


## Compensações, despesas e aditivos

Compensar acrescenta movimento oposto vinculado à origem. A soma não pode superar o original. Devolver entrada exige saldo livre da camada original; recuperar sobra cria camada nova com o custo/lote histórico e não recria reserva. Material indivisível exige quantidade inteira. Consumo vinculado ao pedido só é compensado pelo pedido. Histórico recebido da compra continua cumulativo; compensação física não faz reembolso do fornecedor ou novo recebimento automático.

Custo consumido e necessidades de reposição usam consumo líquido de sobras. Despesas reais são registros positivos; corrigir exige reversão inteira com motivo e novo lançamento. Não alteram pagamentos do cliente. Resultado sobre custos registrados inclui consumo líquido, sessões encerradas/corrigidas e despesas líquidas; desconhecidos/sessão ativa tornam o subtotal parcial, e despesas não lançadas/tributos ainda podem faltar.

Aditivo precisa de aceite da versão exata e pedido aberto. Reservas dos itens alterados/removidos são liberadas; a nova necessidade é reservada explicitamente. Itens retirados permanecem com histórico, marcados como removidos, sem novos trabalhos/entregas. Consumos anteriores não são apagados: alterações exigem motivo de conciliação, e somente sobra física volta ao estoque. Quantidade produzida/entregue não é reduzida; composição de peça já produzida não é substituída por este fluxo.

Média disponível, última camada registrada e referência manual são políticas de estimativa por revisão de ficha. Última camada pode ser recuperação de sobra, não necessariamente compra; referência desconhecida não vira zero. Consumo real continua com custo histórico da camada utilizada.
