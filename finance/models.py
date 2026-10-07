import uuid
from django.conf import settings
from django.db import models


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    method = models.CharField(
        max_length=30,
        choices=[
            ("pix", "Pix"),
            ("cash", "Dinheiro"),
            ("transfer", "Transferência"),
            ("other", "Outro"),
        ],
    )
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payment_amount_positive"
            )
        ]


class PaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        Payment, on_delete=models.PROTECT, related_name="allocation"
    )
    version = models.ForeignKey(
        "sales.QuoteVersion", on_delete=models.PROTECT, related_name="allocations"
    )
    order = models.ForeignKey(
        "production.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="allocations",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="allocation_amount_positive"
            )
        ]


class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.ForeignKey(
        PaymentAllocation, on_delete=models.PROTECT, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="refund_amount_positive"
            )
        ]


class Receivable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "production.Order", on_delete=models.PROTECT, related_name="receivables"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    label = models.CharField(max_length=100, blank=True)
    cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="receivable_amount_positive"
            )
        ]
