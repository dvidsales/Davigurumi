import uuid
from django.conf import settings
from django.db import models


class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField("Nome", max_length=160)
    contact = models.CharField("Contato", max_length=160, blank=True)
    notes = models.TextField("Notas internas", max_length=2000, blank=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Quote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    current_version = models.ForeignKey(
        "QuoteVersion", on_delete=models.PROTECT, null=True, related_name="current_for"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "number"], name="quote_number_per_owner"
            )
        ]


class QuoteVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="versions")
    amends_version = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="amendments",
    )
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        default="draft",
        choices=[
            ("draft", "Rascunho"),
            ("sent", "Enviada"),
            ("approved", "Aprovada"),
            ("declined", "Recusada"),
            ("changes", "Alteração solicitada"),
            ("expired", "Expirada"),
            ("revoked", "Revogada"),
            ("superseded", "Substituída"),
        ],
    )
    terms = models.TextField("Condições para o cliente", max_length=3000, blank=True)
    delivery_date = models.DateField("Prazo de entrega/retirada", null=True, blank=True)
    valid_days = models.PositiveIntegerField(default=15)
    expires_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    public_snapshot = models.JSONField(default=dict, blank=True)
    internal_snapshot = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    pdf = models.BinaryField(default=bytes, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    approved_hash = models.CharField(max_length=64, blank=True)
    approval_origin = models.CharField(
        max_length=12,
        default="link",
        choices=[("link", "Aceite por link"), ("imported", "Histórico importado")],
    )

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["quote", "number"], name="quote_version_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0) & models.Q(valid_days__gt=0),
                name="quote_version_valid_values",
            ),
        ]


class QuoteItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        QuoteVersion, on_delete=models.PROTECT, related_name="items"
    )
    line_key = models.UUIDField(default=uuid.uuid4)
    project_revision = models.ForeignKey(
        "projects.ProjectRevision", on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField()
    description = models.CharField(max_length=300)
    snapshot = models.JSONField(default=dict)
    calculated_price = models.DecimalField(max_digits=12, decimal_places=2)
    manual_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total__gte=0) & models.Q(quantity__gt=0),
                name="quote_item_valid_values",
            )
        ]


class ShareToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        QuoteVersion, on_delete=models.PROTECT, related_name="tokens"
    )
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class QuoteEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        QuoteVersion, on_delete=models.PROTECT, related_name="events"
    )
    kind = models.CharField(max_length=20)
    key = models.UUIDField(null=True, blank=True)
    declaration = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "key"],
                condition=models.Q(key__isnull=False),
                name="portal_request_idempotency",
            )
        ]


class FileAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(upload_to="private")
    label = models.CharField(max_length=160)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.label


class QuoteImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        QuoteVersion, on_delete=models.PROTECT, related_name="images"
    )
    asset = models.ForeignKey(FileAsset, on_delete=models.PROTECT)
    is_public = models.BooleanField(default=False)
