from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from materials.stock import begin_operation, finish
from operations.services import emit
from production.models import Order
from sales.models import QuoteVersion
from .models import Payment, PaymentAllocation, Refund, Receivable


def valid_money(value):
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value <= 0
        or value > Decimal("9999999999.99")
        or value.quantize(Decimal(".01")) != value
    ):
        raise ValidationError(
            "Valor precisa ser positivo, em centavos, dentro do limite suportado."
        )


@transaction.atomic
def record_payment(
    *, owner, version_id, amount, date, method, key, notes="", allow_credit=False
):
    valid_money(amount)
    if method not in {"pix", "cash", "transfer", "other"}:
        raise ValidationError("Forma de pagamento inválida.")
    op, repeated = begin_operation(
        owner,
        key,
        "payment",
        {
            "version": version_id,
            "amount": amount,
            "date": date,
            "method": method,
            "notes": notes,
            "credit": allow_credit,
        },
    )
    if repeated:
        return op.result
    version = get_object_or_404(
        QuoteVersion, pk=version_id, quote__owner=owner, status="approved"
    )
    order = Order.objects.filter(current_version=version).first()
    if order and order.status == "cancelled":
        raise ValidationError("Pedido cancelado não recebe novo pagamento.")
    allocations = (
        PaymentAllocation.objects.filter(order=order)
        if order
        else version.allocations.all()
    )
    net = sum(
        (
            row.amount
            - sum((refund.amount for refund in row.refunds.all()), Decimal(0))
            for row in allocations
        ),
        Decimal(0),
    )
    if net + amount > version.total and not allow_credit:
        raise ValidationError(
            "Valor supera o saldo devido. Confirme explicitamente o crédito/excedente."
        )
    payment = Payment.objects.create(
        owner=owner, amount=amount, date=date, method=method, notes=notes[:200]
    )
    allocation = PaymentAllocation.objects.create(
        payment=payment, version=version, order=order, amount=amount
    )
    emit(
        owner=owner,
        kind="payment_recorded",
        object_id=payment.pk,
        message="Recebimento manual registrado.",
    )
    return finish(op, {"payment": str(payment.pk), "allocation": str(allocation.pk)})


@transaction.atomic
def refund_payment(*, owner, allocation_id, amount, date, reason, key):
    valid_money(amount)
    if not reason.strip():
        raise ValidationError("Informe o motivo do estorno/reembolso.")
    op, repeated = begin_operation(
        owner,
        key,
        "refund",
        {"allocation": allocation_id, "amount": amount, "date": date, "reason": reason},
    )
    if repeated:
        return op.result
    allocation = get_object_or_404(
        PaymentAllocation.objects.select_for_update(),
        pk=allocation_id,
        payment__owner=owner,
    )
    refunded = sum((row.amount for row in allocation.refunds.all()), Decimal(0))
    if refunded + amount > allocation.amount:
        raise ValidationError(
            "Estorno não pode superar o recebido líquido deste lançamento."
        )
    refund = Refund.objects.create(
        allocation=allocation, amount=amount, date=date, reason=reason[:200]
    )
    emit(
        owner=owner,
        kind="payment_refunded",
        object_id=refund.pk,
        message="Estorno/reembolso manual registrado.",
    )
    return finish(op, {"refund": str(refund.pk)})


@transaction.atomic
def add_receivable(*, owner, order_id, amount, due_date, label=""):
    valid_money(amount)
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    order = get_object_or_404(Order, pk=order_id, owner=owner)
    if order.status == "cancelled":
        raise ValidationError("Pedido cancelado não recebe nova cobrança prevista.")
    scheduled = sum(
        (row.amount for row in order.receivables.filter(cancelled=False)), Decimal(0)
    )
    if scheduled + amount > order.total:
        raise ValidationError(
            "Parcelas previstas não podem superar o total comercial vigente."
        )
    return Receivable.objects.create(
        order=order, amount=amount, due_date=due_date, label=label[:100]
    )


def installment_balances(order):
    """Apply net receipts oldest-due-first for due indicators without duplicating cash."""
    remaining = order.net_received
    result = []
    for row in order.receivables.filter(cancelled=False):
        applied = min(row.amount, remaining)
        remaining -= applied
        result.append({"receivable": row, "balance": row.amount - applied})
    return result
