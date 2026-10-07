# Contratos de negócio

Referência: seções 53–76 do PRD extraído. Propostas do PDF continuam identificadas
como propostas quando dependem de decisão de negócio. Esta entrega valida apenas
abertura de estoque e cálculo isolado; não simula aprovação dessas decisões.

## Implementado

**Materiais:** nome/tipo/unidade essenciais; marca/cor/código/tex/notas opcionais.
Tex positivo apenas em fios. Unidades base iniciais: g, m, un. `un` é indivisível.
Conversão de novelo para gramas ainda não existe: informe quantidade já na unidade base.

**Abertura:** material e entrada criados em uma transação; quantidade zero cria somente
material. Sem fornecedor nem compra fictícios. Custo nulo é desconhecido; custo zero
é um valor conhecido. O custo informado se refere à unidade base, não à embalagem.
Histórico é a origem do saldo. Mesma chave de formulário/dono retorna o mesmo cadastro;
reenvio alterado é rejeitado. Um formulário novo representa um novo cadastro.

Quantidade e custo unitário são limitados nesta versão a 999999,999999 (12 dígitos,
seis decimais), para não prometer a precisão de NUMERIC PostgreSQL na representação
numérica do SQLite. O valor máximo foi testado após recarregar o banco. Aumentar esse
limite exige PostgreSQL e teste de persistência; não apenas mudar o formulário.

**Cálculo (§59):** usa `Decimal`, sem float. Custo = materiais + horas × valor/hora +
adicionais. Markup: `P0 = C × (1 + k)`. Margem: `P0 = C / (1 − m − t)`.
Desconto: `P = P0 × (1 − d) − D`. Taxas no markup são deduzidas do resultado, sem
aumentar P0. Resultado = preço final × (1 − t) − custo. Margem efetiva = resultado/preço;
preço zero tem margem indefinida. Valores apresentados usam half-up em centavos;
intermediários usam precisão maior. Resultado usa o preço final arredondado.

Validar números finitos, custo/percentuais não negativos, taxa < 100%, desconto de 0 a
100%, `m + t < 100%` e preço não negativo. Venda abaixo do custo gera aviso. A calculadora
é exploratória: não guarda snapshot, não publica preço nem garante que todos os custos
foram informados. Custo desconhecido de material não é integrado automaticamente aqui.

## Contratos a implementar nas próximas entregas

- Físico = entradas − saídas; disponível = físico − reserva. Reserva não consome.
  Exemplo obrigatório: 508/120/388 → consumir 50 reservado → 458/70/388 → liberar 70
  → 458/0/458. Transações e locks PostgreSQL precisam de teste concorrente real.
- Confirmar compra não recebe. Receber parcial gera camada/movimento/custo atomicamente.
  Repetição cria rascunho; correção compensa, não apaga. Rateio determinístico de centavos.
- Estimativa, alocação física e valorização realizada são distintas. Propostas: média
  ponderada disponível, FIFO físico e custo específico de camada. Teste 100g×0,10 +
  100g×0,20: estimar 120g custa 12/24/18; consumir FIFO custa 14.
- Publicar congela versão, imagens e condições. Nova versão invalida aprovação da anterior
  sem apagar histórico. GET nunca aprova. Aceite e pedido têm unicidade/idempotência.
- Portal e PDF expõem somente identidade comercial mínima, itens, preço, imagens
  selecionadas, prazos, validade, condições e aceite; nunca custo/margem/notas/estoque.
- Produção, entrega e financeiro possuem estados independentes. Cancelamento libera
  reserva remanescente, conserva consumo e pagamentos; sobra real retorna por movimento.
- Cronômetro usa timestamps/sessões do servidor, não contador local persistido por segundo.
- Cobrança prevista não é recebimento. Recebimento 50 + 30 − estorno 10 num pedido 100
  implica líquido 70 e a receber 30. Sinal convertido em pedido não replica pagamento.
- Importações têm prévia, revalidação, limite e idempotência; não executam fórmulas/macros.
  Exportação relacional conserva vínculos e arquivos, com round trip verificável.
- Demo isolada não envia comunicações reais nem copia saldos/pagamentos implicitamente.
- Eliminação de dados pessoais alcança snapshots/arquivos/logs; tombstones reaplicados
  após restauração. Política depende de finalidade/retenção, não de imutabilidade eterna.
