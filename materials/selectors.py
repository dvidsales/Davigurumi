"""Read-only projections; the stock ledger remains authoritative."""

from decimal import Decimal
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from .models import Material, StockMovement, CostLayer


def stock_levels(owner):
    field = DecimalField(max_digits=24, decimal_places=6)

    def total(model, column):
        rows = (
            model.objects.filter(material_id=OuterRef("pk"))
            .order_by()
            .values("material_id")
            .annotate(total=Sum(column))
            .values("total")
        )
        return Coalesce(
            Subquery(rows, output_field=field), Value(Decimal(0), output_field=field)
        )

    return (
        Material.objects.filter(owner=owner)
        .annotate(
            ledger_physical=total(StockMovement, "quantity"),
            ledger_reserved=total(CostLayer, "reserved"),
        )
        .annotate(ledger_available=F("ledger_physical") - F("ledger_reserved"))
    )
