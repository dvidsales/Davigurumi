import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationPreference(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email_enabled = models.BooleanField(
        "Receber notificações por e-mail", default=False
    )


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=150)
    message = models.CharField(max_length=240)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "key"], name="notification_event_unique"
            )
        ]


class OutboxEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.OneToOneField(Notification, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=12,
        default="pending",
        choices=[
            ("pending", "Pendente"),
            ("sent", "Enviada"),
            ("imported", "Histórico importado"),
        ],
    )
    attempts = models.PositiveIntegerField(default=0)
    next_attempt = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    object_id = models.UUIDField()
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
