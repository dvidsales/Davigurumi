"""Read projections used by summaries, without loading commercial PDFs."""

from decimal import Decimal
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from finance.models import PaymentAllocation, Refund
from .models import Order


def outstanding_balances(owner):
    field = DecimalField(max_digits=24, decimal_places=2)

    def total(model, relation):
        query = (
            model.objects.filter(**{relation: OuterRef("pk")})
            .order_by()
            .values(relation)
            .annotate(total=Sum("amount"))
            .values("total")
        )
        return Coalesce(
            Subquery(query, output_field=field), Value(Decimal(0), output_field=field)
        )

    # Independent subqueries prevent payment/refund joins multiplying amounts.
    return (
        Order.objects.filter(owner=owner)
        .exclude(status="cancelled")
        .annotate(
            ledger_paid=total(PaymentAllocation, "order_id"),
            ledger_refunded=total(Refund, "allocation__order_id"),
        )
        .annotate(
            ledger_balance=Greatest(
                F("current_version__total") - F("ledger_paid") + F("ledger_refunded"),
                Value(Decimal(0), output_field=field),
                output_field=field,
            )
        )
    )
