"""Limits are checked under the owner lock, including imports and demo copies."""

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Length
from .privacy import assert_not_erased

SCOPES = {
    "materials.material": "owner",
    "projects.project": "owner",
    "sales.client": "owner",
    "sales.quote": "owner",
    "purchasing.supplier": "owner",
    "purchasing.purchase": "owner",
    "production.order": "owner",
    "materials.stockoperation": "owner",
    "projects.projectrevision": "project__owner",
    "sales.quoteversion": "quote__owner",
}


@transaction.atomic
def ensure_capacity(owner, label, additional=1):
    current = get_user_model().objects.select_for_update().get(pk=owner.pk)
    if not current.is_active:
        raise ValidationError("Acesso suspenso; operação bloqueada.")
    assert_not_erased(owner.pk)
    limit = settings.ACCOUNT_RECORD_LIMITS.get(label)
    if limit is None:
        return
    total = apps.get_model(label).objects.filter(**{SCOPES[label]: owner}).count()
    if total + additional > limit:
        raise ValidationError(
            "Limite de registros da conta atingido. Preserve o histórico e consulte o responsável pelo ambiente."
        )


@transaction.atomic
def ensure_storage(owner, additional):
    current = get_user_model().objects.select_for_update().get(pk=owner.pk)
    if not current.is_active:
        raise ValidationError("Acesso suspenso; operação bloqueada.")
    assert_not_erased(owner.pk)
    image_bytes = (
        apps.get_model("sales.fileasset")
        .objects.filter(owner=owner)
        .aggregate(total=Sum("size"))["total"]
        or 0
    )
    pdf_bytes = (
        apps.get_model("sales.quoteversion")
        .objects.filter(quote__owner=owner)
        .aggregate(total=Sum(Length("pdf")))["total"]
        or 0
    )
    if image_bytes + pdf_bytes + additional > settings.ACCOUNT_STORAGE_LIMIT:
        raise ValidationError(
            "Limite de armazenamento privado da conta atingido. Preserve o histórico e consulte o responsável pelo ambiente."
        )
