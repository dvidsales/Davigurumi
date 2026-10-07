import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField("Nome", max_length=160)
    contact = models.CharField("Contato", max_length=160, blank=True)
    notes = models.TextField("Observações", blank=True, max_length=2000)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Purchase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True
    )
    date = models.DateField("Data")
    freight = models.DecimalField(
        "Frete (R$)", max_digits=12, decimal_places=2, default=0
    )
    discount = models.DecimalField(
        "Desconto da compra (R$)", max_digits=12, decimal_places=2, default=0
    )
    notes = models.TextField("Observações", blank=True, max_length=2000)
    status = models.CharField(
        max_length=20,
        default="draft",
        choices=[
            ("draft", "Rascunho"),
            ("confirmed", "Confirmada"),
            ("partial", "Parcialmente recebida"),
            ("received", "Recebida"),
            ("cancelled", "Cancelada"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    allocation_mode = models.CharField(
        max_length=10,
        default="auto",
        choices=[("auto", "Proporcional"), ("manual", "Manual")],
    )

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(freight__gte=0) & models.Q(discount__gte=0),
                name="purchase_charges_nonnegative",
            )
        ]

    @property
    def item_total(self):
        return sum((item.net_total for item in self.items.all()), Decimal(0))

    @property
    def total(self):
        return self.item_total + self.freight - self.discount

    def __str__(self):
        return f"Compra {self.date:%d/%m/%Y}"


class PurchaseItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name="items"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=6)
    unit = models.CharField(max_length=40)
    base_quantity = models.DecimalField(max_digits=12, decimal_places=6)
    conversion_snapshot = models.JSONField(default=dict)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    received = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    allocated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    lot = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0)
                & models.Q(base_quantity__gt=0)
                & models.Q(unit_price__gte=0),
                name="purchase_item_valid_values",
            ),
            models.CheckConstraint(
                condition=models.Q(received__gte=0)
                & models.Q(received__lte=models.F("base_quantity")),
                name="purchase_item_received_within_order",
            ),
        ]

    @property
    def net_total(self):
        from decimal import ROUND_HALF_UP

        return (self.quantity * self.unit_price).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )

    @property
    def remaining(self):
        return self.base_quantity - self.received


class Receipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name="receipts"
    )
    key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(PurchaseItem, on_delete=models.PROTECT)
    layer = models.OneToOneField("materials.CostLayer", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=6)
