import uuid
from django.conf import settings
from django.db import models


class ImportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rows = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    headers = models.JSONField(default=list)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
