import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("e-mail", unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="user_email_case_insensitive_unique"
            )
        ]


class AuthThrottle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class DemoWorkspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="demo_workspace",
    )
    demo_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demo_identity"
    )
    created_at = models.DateTimeField(auto_now_add=True)
