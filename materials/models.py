import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models


class Material(models.Model):
    class Kind(models.TextChoices):
        YARN = "yarn", "Fio"
        FABRIC = "fabric", "Tecido"
        FILLING = "filling", "Enchimento"
        ACCESSORY = "accessory", "Acessório"
        PACKAGING = "packaging", "Embalagem"
        OTHER = "other", "Outro material"

    class Unit(models.TextChoices):
        GRAM = "g", "Gramas (g)"
        METER = "m", "Metros (m)"
        PIECE = "un", "Unidades (un)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField("Nome", max_length=160)
    kind = models.CharField("Tipo", max_length=20, choices=Kind.choices)
    unit = models.CharField("Unidade de estoque", max_length=2, choices=Unit.choices)
    brand = models.CharField("Marca", max_length=100, blank=True)
    color = models.CharField("Cor", max_length=100, blank=True)
    color_code = models.CharField("Código da cor", max_length=40, blank=True)
    tex = models.DecimalField(
        "Tex (somente fios)", max_digits=12, decimal_places=3, null=True, blank=True
    )
    composition = models.CharField("Composição", max_length=160, blank=True)
    thickness = models.CharField(
        "Espessura / título comercial", max_length=100, blank=True
    )
    recommended_hook = models.CharField(
        "Agulha recomendada", max_length=100, blank=True
    )
    minimum_stock = models.DecimalField(
        "Estoque mínimo disponível", max_digits=12, decimal_places=6, default=0
    )
    notes = models.TextField("Observações internas", blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["owner", "name"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(minimum_stock__gte=0),
                name="material_minimum_stock_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tex__isnull=True) | models.Q(tex__gt=0),
                name="material_positive_tex",
            ),
            models.UniqueConstraint(
                fields=["owner", "request_key"], name="material_creation_idempotency"
            ),
        ]

    @property
    def physical_stock(self):
        return sum(
            (movement.quantity for movement in self.movements.all()), Decimal("0")
        )

    @property
    def reserved_stock(self):
        return sum((layer.reserved for layer in self.layers.all()), Decimal("0"))

    @property
    def available_stock(self):
        return self.physical_stock - self.reserved_stock

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    """Signed physical ledger; reservation events never change physical quantity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="movements"
    )
    layer = models.ForeignKey(
        "CostLayer",
        on_delete=models.PROTECT,
        related_name="movements",
        null=True,
        blank=True,
    )
    kind = models.CharField(
        max_length=20,
        default="opening",
        choices=[
            ("opening", "Estoque inicial"),
            ("receipt", "Recebimento"),
            ("consumption", "Consumo"),
            ("loss", "Perda"),
            ("return", "Sobra recuperada"),
            ("adjustment", "Ajuste"),
        ],
    )
    quantity = models.DecimalField("Quantidade", max_digits=12, decimal_places=6)
    unit_cost = models.DecimalField(
        "Custo por unidade base", max_digits=12, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=100, default="Estoque inicial")
    conversion_snapshot = models.JSONField(default=dict, blank=True)
    operation = models.ForeignKey(
        "StockOperation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
    )
    reverses = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="movement_quantity_nonzero"
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="opening") | models.Q(quantity__gt=0),
                name="opening_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__isnull=True) | models.Q(unit_cost__gte=0),
                name="opening_cost_nonnegative",
            ),
            models.UniqueConstraint(
                fields=["material"],
                condition=models.Q(kind="opening"),
                name="one_opening_per_material",
            ),
        ]


class MaterialConversion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="conversions"
    )
    name = models.CharField(max_length=40)
    factor = models.DecimalField(max_digits=12, decimal_places=6)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["material", "name", "version"], name="conversion_version_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(factor__gt=0), name="conversion_positive_factor"
            ),
        ]


class CostLayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="layers"
    )
    lot = models.CharField("Lote de fabricação", max_length=80, blank=True)
    original_quantity = models.DecimalField(max_digits=12, decimal_places=6)
    physical = models.DecimalField(max_digits=12, decimal_places=6)
    reserved = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(physical__gte=0), name="layer_physical_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(reserved__gte=0), name="layer_reserved_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(reserved__lte=models.F("physical")),
                name="layer_reserved_within_physical",
            ),
            models.CheckConstraint(
                condition=models.Q(original_quantity__gt=0),
                name="layer_original_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__isnull=True) | models.Q(unit_cost__gte=0),
                name="layer_cost_nonnegative",
            ),
        ]


class StockOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    action = models.CharField(max_length=40)
    payload_hash = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "key"], name="stock_operation_idempotency"
            )
        ]


class StockReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    layer = models.ForeignKey(
        CostLayer, on_delete=models.PROTECT, related_name="reservations"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=6)
    remaining = models.DecimalField(max_digits=12, decimal_places=6)
    reference = models.UUIDField(null=True, blank=True)
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="reservation_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(remaining__gte=0)
                & models.Q(remaining__lte=models.F("quantity")),
                name="reservation_remaining_valid",
            ),
        ]


class ReservationEvent(models.Model):
    reservation = models.ForeignKey(
        StockReservation, on_delete=models.PROTECT, related_name="events"
    )
    operation = models.ForeignKey(StockOperation, on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=20,
        choices=[
            ("reserve", "Reserva"),
            ("consume", "Consumo reservado"),
            ("release", "Liberação"),
        ],
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)
