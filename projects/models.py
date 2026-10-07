import uuid
from django.conf import settings
from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField("Nome", max_length=160)
    notes = models.TextField("Notas internas", blank=True, max_length=2000)
    current_revision = models.ForeignKey(
        "ProjectRevision",
        on_delete=models.PROTECT,
        null=True,
        related_name="current_for",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class ProjectRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="revisions"
    )
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=2000)
    technique = models.CharField(max_length=100, blank=True)
    base_quantity = models.PositiveIntegerField(default=1)
    estimated_seconds = models.PositiveIntegerField(default=0)
    reference_policy = models.CharField(
        "Referência de custo",
        max_length=12,
        default="available",
        choices=[
            ("available", "Média do estoque disponível"),
            ("latest", "Última camada registrada"),
            ("manual", "Referência manual da ficha"),
        ],
    )
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    additional_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mode = models.CharField(
        max_length=10,
        default="markup",
        choices=[("markup", "Markup"), ("margin", "Margem")],
    )
    percentage = models.DecimalField(max_digits=7, decimal_places=4, default=".5")
    fee = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "number"], name="project_revision_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(base_quantity__gt=0)
                & models.Q(hourly_rate__gte=0)
                & models.Q(additional_cost__gte=0),
                name="project_revision_valid_cost",
            ),
        ]


class ProjectMaterial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        ProjectRevision, on_delete=models.PROTECT, related_name="materials"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=6)
    unit = models.CharField(max_length=40)
    base_quantity = models.DecimalField(max_digits=12, decimal_places=6)
    conversion_snapshot = models.JSONField(default=dict)
    manual_unit_cost = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0) & models.Q(base_quantity__gt=0),
                name="project_material_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(manual_unit_cost__isnull=True)
                | models.Q(manual_unit_cost__gte=0),
                name="project_material_manual_cost_valid",
            ),
        ]


class MaterialAlternative(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(
        ProjectMaterial, on_delete=models.PROTECT, related_name="alternatives"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    base_quantity = models.DecimalField(max_digits=12, decimal_places=6)
    note = models.CharField(max_length=200, blank=True)
