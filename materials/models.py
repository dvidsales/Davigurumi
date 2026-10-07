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
    tex = models.DecimalField("Tex (somente fios)", max_digits=12, decimal_places=3, null=True, blank=True)
    notes = models.TextField("Observações internas", blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["owner", "name"])]
        constraints = [models.CheckConstraint(condition=models.Q(tex__isnull=True) | models.Q(tex__gt=0), name="material_positive_tex"),
                       models.UniqueConstraint(fields=["owner", "request_key"], name="material_creation_idempotency")]

    @property
    def physical_stock(self):
        return sum((movement.quantity for movement in self.movements.all()), Decimal("0"))

    def __str__(self):
        return self.name

class StockMovement(models.Model):
    """This first slice supports immutable opening entries, not purchase/consumption yet."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="movements")
    quantity = models.DecimalField("Quantidade", max_digits=12, decimal_places=6)
    unit_cost = models.DecimalField("Custo por unidade base", max_digits=12, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=100, default="Estoque inicial")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="opening_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_cost__isnull=True) | models.Q(unit_cost__gte=0), name="opening_cost_nonnegative"),
            models.UniqueConstraint(fields=["material"], name="one_opening_per_material"),
        ]
