import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    approved_version = models.OneToOneField(
        "sales.QuoteVersion", on_delete=models.PROTECT, related_name="initial_order"
    )
    current_version = models.ForeignKey(
        "sales.QuoteVersion", on_delete=models.PROTECT, related_name="current_orders"
    )
    status = models.CharField(
        max_length=20,
        default="waiting",
        choices=[
            ("waiting", "Aguardando"),
            ("in_progress", "Em produção"),
            ("paused", "Pausada"),
            ("completed", "Concluída"),
            ("cancelled", "Cancelada"),
        ],
    )
    delivery_status = models.CharField(
        max_length=20,
        default="not_sent",
        choices=[
            ("not_sent", "Não enviada"),
            ("ready", "Pronta para retirada"),
            ("sent", "Enviada"),
            ("delivered", "Entregue"),
        ],
    )
    production_due = models.DateField("Prazo de produção", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    @property
    def total(self):
        return self.current_version.total

    @property
    def net_received(self):
        total = Decimal(0)
        for allocation in self.allocations.select_related("payment"):
            total += allocation.amount - sum(
                (refund.amount for refund in allocation.refunds.all()), Decimal(0)
            )
        return total

    @property
    def balance(self):
        return max(Decimal(0), self.total - self.net_received)

    @property
    def credit(self):
        return max(Decimal(0), self.net_received - self.total)

    @property
    def financial_status(self):
        paid = self.net_received
        if self.status == "cancelled" and paid > 0:
            return "Pendência de reembolso"
        if paid > self.total:
            return "Crédito/excedente"
        if paid == self.total:
            return "Quitado"
        return "Parcial" if paid > 0 else "Em aberto"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    source_item = models.OneToOneField("sales.QuoteItem", on_delete=models.PROTECT)
    line_key = models.UUIDField(default=uuid.uuid4)
    description = models.CharField(max_length=300)
    quantity = models.PositiveIntegerField()
    produced = models.PositiveIntegerField(default=0)
    delivered = models.PositiveIntegerField(default=0)
    snapshot = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(produced__lte=models.F("quantity"))
                & models.Q(delivered__lte=models.F("produced")),
                name="order_item_progress_valid",
            ),
            models.UniqueConstraint(
                fields=["order", "line_key"], name="order_line_identity_unique"
            ),
        ]


class Consumption(models.Model):
    item = models.ForeignKey(
        OrderItem, on_delete=models.PROTECT, related_name="consumptions"
    )
    movement = models.OneToOneField("materials.StockMovement", on_delete=models.PROTECT)


class ProductionSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    item = models.ForeignKey(
        OrderItem, on_delete=models.PROTECT, related_name="sessions"
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    seconds = models.PositiveIntegerField(default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    origin = models.CharField(
        max_length=12,
        default="timer",
        choices=[("timer", "Cronômetro"), ("manual", "Manual")],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner"],
                condition=models.Q(ended_at__isnull=True),
                name="one_active_session_per_owner",
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True)
                | models.Q(ended_at__gte=models.F("started_at")),
                name="session_timestamps_valid",
            ),
        ]

    @property
    def effective_seconds(self):
        correction = self.corrections.order_by("-created_at", "-id").first()
        return correction.seconds if correction else self.seconds


class SessionCorrection(models.Model):
    session = models.ForeignKey(
        ProductionSession, on_delete=models.PROTECT, related_name="corrections"
    )
    seconds = models.PositiveIntegerField()
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class DeliveryEvent(models.Model):
    item = models.ForeignKey(
        OrderItem, on_delete=models.PROTECT, related_name="deliveries"
    )
    quantity = models.PositiveIntegerField()
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
