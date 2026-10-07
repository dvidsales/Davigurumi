from collections import defaultdict
from decimal import Decimal
from django import forms
from django.db.models import Sum
from django.utils import timezone
from finance.models import Payment, Refund
from materials.models import Material, StockReservation
from production.models import Order, ProductionSession
from sales.models import QuoteVersion


class PeriodForm(forms.Form):
    start = forms.DateField(
        label="De", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Até", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end"):
            if data["end"] < data["start"]:
                raise forms.ValidationError(
                    "A data final deve ser igual ou posterior à inicial."
                )
            if (data["end"] - data["start"]).days > 3660:
                raise forms.ValidationError("Escolha um período de até 10 anos.")
        return data


def cash_period(owner, start, end):
    received = Payment.objects.filter(owner=owner, date__range=(start, end)).aggregate(
        total=Sum("amount")
    )["total"] or Decimal(0)
    refunded = Refund.objects.filter(
        allocation__payment__owner=owner, date__range=(start, end)
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    return {"receipts": received, "refunds": refunded, "net": received - refunded}


def replenishment(owner):
    """Remaining requirements subtract actual consumption and this item's reserves.
    Compare the sum of uncovered needs with free stock (already excludes every reserve).
    """
    required = defaultdict(Decimal)
    orders = Order.objects.filter(
        owner=owner, status__in=["waiting", "in_progress", "paused"]
    ).prefetch_related("items__consumptions__movement")
    for order in orders:
        for item in order.items.all():
            requirements = defaultdict(Decimal)
            for line in item.snapshot.get("materials", []):
                requirements[line["material"]] += Decimal(line["quantity"])
            for material_id, quantity in requirements.items():
                consumed = sum(
                    (
                        -entry.movement.quantity
                        for entry in item.consumptions.all()
                        if str(entry.movement.material_id) == material_id
                    ),
                    Decimal(0),
                )
                reserved = StockReservation.objects.filter(
                    reference=item.pk,
                    layer__material_id=material_id,
                    layer__material__owner=owner,
                ).aggregate(total=Sum("remaining"))["total"] or Decimal(0)
                required[material_id] += max(Decimal(0), quantity - consumed - reserved)
    rows = []
    for material in Material.objects.filter(
        owner=owner, pk__in=required
    ).prefetch_related("movements", "layers"):
        shortage = max(
            Decimal(0), required[str(material.pk)] - material.available_stock
        )
        if shortage:
            rows.append(
                {
                    "material": material,
                    "quantity": shortage,
                    "required": required[str(material.pk)],
                }
            )
    return rows


def overview(owner):
    today = timezone.localdate()
    orders = (
        Order.objects.filter(owner=owner)
        .select_related("current_version")
        .prefetch_related("allocations__refunds")
    )
    active = orders.filter(status__in=["waiting", "in_progress", "paused"])
    balances = sum(
        (order.balance for order in orders.exclude(status="cancelled")), Decimal(0)
    )
    return {
        "active_orders": active.count(),
        "late_orders": active.filter(production_due__lt=today).count(),
        "open_balance": balances,
        "pending_quotes": QuoteVersion.objects.filter(
            quote__owner=owner, status="sent", expires_at__gt=timezone.now()
        ).count(),
        "active_session": ProductionSession.objects.filter(
            owner=owner, ended_at__isnull=True
        )
        .select_related("item__order")
        .first(),
        "cash": cash_period(owner, today.replace(day=1), today),
        "shortages": replenishment(owner),
    }
