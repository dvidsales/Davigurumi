import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("e-mail", unique=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive_unique")]
