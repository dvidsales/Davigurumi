"""Pure pricing prototype of PRD §59. No quote publication or financial entries."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext

ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")

@dataclass(frozen=True)
class PriceResult:
    cost: Decimal
    base_price: Decimal
    sale_price: Decimal
    profit: Decimal
    effective_margin: Decimal | None

def calculate_price(*, cost: Decimal, mode: str, percentage: Decimal, fee: Decimal = ZERO,
                    discount: Decimal = ZERO, fixed_discount: Decimal = ZERO) -> PriceResult:
    values = (cost, percentage, fee, discount, fixed_discount)
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
        raise ValueError("Use valores decimais finitos.")
    if cost < 0 or percentage < 0 or fixed_discount < 0:
        raise ValueError("Custos, percentuais e desconto fixo não podem ser negativos.")
    if not ZERO <= fee < ONE or not ZERO <= discount <= ONE:
        raise ValueError("Taxa deve ser menor que 100% e desconto deve ficar entre 0% e 100%.")
    if mode not in ("markup", "margin"):
        raise ValueError("Escolha markup ou margem.")
    if mode == "margin" and percentage + fee >= ONE:
        raise ValueError("Margem e taxas somadas precisam ser menores que 100%.")
    with localcontext() as context:
        context.prec = 40
        base = cost * (ONE + percentage) if mode == "markup" else cost / (ONE - percentage - fee)
        sale = base * (ONE - discount) - fixed_discount
        if sale < ZERO:
            raise ValueError("O desconto não pode gerar um preço negativo.")
        sale = sale.quantize(CENT, rounding=ROUND_HALF_UP)
        profit = sale * (ONE - fee) - cost
        margin = profit / sale if sale > ZERO else None
        return PriceResult(cost.quantize(CENT, rounding=ROUND_HALF_UP),
                           base.quantize(CENT, rounding=ROUND_HALF_UP), sale,
                           profit.quantize(CENT, rounding=ROUND_HALF_UP), margin)
