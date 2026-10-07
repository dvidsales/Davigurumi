import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from operations.services import emit
from projects.models import Project
from projects.services import snapshot_project
from pricing.domain import calculate_price
from .models import Client, Quote, QuoteVersion, QuoteItem, ShareToken, QuoteEvent
from .pdf import generate_pdf


@transaction.atomic
def create_quote(
    *,
    owner,
    client_id=None,
    client_name="",
    client_contact="",
    terms="",
    delivery_date=None,
    valid_days=15,
):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    if client_id and client_name:
        raise ValidationError("Escolha um cliente existente ou cadastre um novo.")
    client = get_object_or_404(Client, pk=client_id, owner=owner) if client_id else None
    if client_name:
        from accounts.partners import register_contact

        client = register_contact(Client, owner, client_name, client_contact)
    if not 1 <= valid_days <= 365:
        raise ValidationError("Validade deve ficar entre 1 e 365 dias.")
    number = (
        Quote.objects.filter(owner=owner).aggregate(number=Max("number"))["number"] or 0
    ) + 1
    from accounts.quotas import ensure_capacity

    ensure_capacity(owner, "sales.quote")
    ensure_capacity(owner, "sales.quoteversion")
    quote = Quote.objects.create(owner=owner, client=client, number=number)
    QuoteVersion.objects.create(
        quote=quote,
        number=1,
        terms=terms,
        delivery_date=delivery_date,
        valid_days=valid_days,
    )
    return quote


@transaction.atomic
def add_quote_item(
    *,
    owner,
    version_id,
    project_id,
    quantity,
    description="",
    manual_price=None,
    discount=Decimal(0),
    fixed_discount=Decimal(0),
    choices=None,
):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(
        QuoteVersion.objects.select_for_update(), pk=version_id, quote__owner=owner
    )
    if version.published_at is not None:
        raise ValidationError(
            "Esta versão já foi publicada. Crie outra versão para modificar."
        )
    if version.items.count() >= 50:
        raise ValidationError("Limite de 50 itens por versão.")
    project = get_object_or_404(Project, pk=project_id, owner=owner)
    snapshot = snapshot_project(
        owner=owner,
        revision_id=project.current_revision_id,
        quantity=quantity,
        choices=choices,
    )
    result = calculate_price(
        cost=Decimal(snapshot["cost"]),
        mode=snapshot["mode"],
        percentage=Decimal(snapshot["percentage"]),
        fee=Decimal(snapshot["fee"]),
        discount=discount,
        fixed_discount=fixed_discount,
    )
    if manual_price is not None and (not manual_price.is_finite() or manual_price < 0):
        raise ValidationError("Preço manual precisa ser não negativo.")
    snapshot.update(
        {
            "discount": str(discount),
            "fixed_discount": str(fixed_discount),
            "calculated_price": str(result.sale_price),
        }
    )
    item = QuoteItem(
        version=version,
        project_revision=project.current_revision,
        quantity=quantity,
        description=description or snapshot["name"],
        snapshot=snapshot,
        calculated_price=result.sale_price,
        manual_price=manual_price,
        total=manual_price if manual_price is not None else result.sale_price,
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def new_version(*, owner, quote_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    quote = get_object_or_404(
        Quote.objects.select_for_update(), pk=quote_id, owner=owner
    )
    latest = quote.versions.order_by("-number").first()
    if latest.published_at is None:
        return latest
    from accounts.quotas import ensure_capacity

    ensure_capacity(owner, "sales.quoteversion")
    version = QuoteVersion.objects.create(
        quote=quote,
        number=latest.number + 1,
        terms=latest.terms,
        delivery_date=latest.delivery_date,
        valid_days=latest.valid_days,
        amends_version=(
            quote.current_version
            if quote.current_version and quote.current_version.status == "approved"
            else None
        ),
    )
    for item in latest.items.all():
        QuoteItem.objects.create(
            version=version,
            line_key=item.line_key,
            project_revision=item.project_revision,
            quantity=item.quantity,
            description=item.description,
            snapshot=item.snapshot,
            calculated_price=item.calculated_price,
            manual_price=item.manual_price,
            total=item.total,
        )
    from .models import QuoteImage

    for image in latest.images.all():
        QuoteImage.objects.create(
            version=version, asset=image.asset, is_public=image.is_public
        )
    return version


@transaction.atomic
def remove_draft_item(*, owner, item_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    item = get_object_or_404(
        QuoteItem.objects.select_related("version"),
        pk=item_id,
        version__quote__owner=owner,
    )
    if item.version.published_at:
        raise ValidationError("Itens publicados são imutáveis.")
    version_id = item.version_id
    item.delete()
    return version_id


@transaction.atomic
def edit_draft_item(*, owner, item_id, **values):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    original = get_object_or_404(
        QuoteItem.objects.select_related("version"),
        pk=item_id,
        version__quote__owner=owner,
    )
    if original.version.published_at:
        raise ValidationError("Crie uma nova versão/aditivo para editar este item.")
    line_key = original.line_key
    version_id = original.version_id
    original.delete()
    item = add_quote_item(owner=owner, version_id=version_id, **values)
    item.line_key = line_key
    item.save(update_fields=["line_key"])
    return item


@transaction.atomic
def edit_draft_version(*, owner, version_id, terms, delivery_date, valid_days):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(
        QuoteVersion.objects.select_for_update(), pk=version_id, quote__owner=owner
    )
    if version.published_at:
        raise ValidationError(
            "Condições publicadas são imutáveis; crie uma nova versão/aditivo."
        )
    if not 1 <= valid_days <= 365:
        raise ValidationError("Validade inválida.")
    version.terms = terms
    version.delivery_date = delivery_date
    version.valid_days = valid_days
    version.save(update_fields=["terms", "delivery_date", "valid_days"])
    return version


def make_token(version):
    raw = secrets.token_urlsafe(32)
    ShareToken.objects.create(
        version=version,
        digest=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=version.expires_at,
    )
    return raw


@transaction.atomic
def publish(*, owner, version_id, confirm_limitations=False, confirm_below_cost=False):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(
        QuoteVersion.objects.select_for_update().select_related("quote"),
        pk=version_id,
        quote__owner=owner,
    )
    quote = Quote.objects.select_for_update().get(pk=version.quote_id)
    if version.published_at:
        raise ValidationError(
            "Versão já publicada; use Gerar novo link para compartilhar novamente."
        )
    if quote.versions.filter(number__gt=version.number).exists():
        raise ValidationError("Somente a revisão mais recente pode ser publicada.")
    if (
        quote.current_version_id
        and quote.current_version.status == "approved"
        and version.amends_version_id != quote.current_version_id
    ):
        raise ValidationError(
            "O orçamento já foi aprovado. Alteração comercial exige um aditivo vinculado à aprovação anterior."
        )
    items = list(version.items.all())
    if not items:
        raise ValidationError("Adicione pelo menos um item.")
    for item in items:
        if not item.snapshot["complete"] and (
            item.manual_price is None or not confirm_limitations
        ):
            raise ValidationError(
                "Há custo desconhecido. Informe preço manual e confirme explicitamente a limitação."
            )
        if (
            item.total * (1 - Decimal(item.snapshot["fee"]))
            < Decimal(item.snapshot["cost"])
            and not confirm_below_cost
        ):
            raise ValidationError(
                "Preço abaixo do custo após taxas. Confirme o aviso antes de publicar."
            )
    now = timezone.now()
    version.expires_at = now + timedelta(days=version.valid_days)
    version.total = sum((item.total for item in items), Decimal(0))
    public = {
        "schema": 1,
        "number": quote.number,
        "version": version.number,
        "issuer": owner.first_name or "Davigurumi",
        "items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "total": str(item.total),
            }
            for item in items
        ],
        "total": str(version.total),
        "terms": version.terms,
        "delivery_date": (
            version.delivery_date.isoformat() if version.delivery_date else None
        ),
        "expires_at": timezone.localtime(version.expires_at).isoformat(),
    }
    images = list(version.images.filter(is_public=True).select_related("asset"))
    if any(image.asset.owner_id != owner.pk for image in images):
        raise ValidationError("Imagem não pertence ao emissor.")
    public["images"] = [
        {
            "id": str(image.asset_id),
            "label": image.asset.label,
            "hash": image.asset.sha256,
        }
        for image in images
    ]
    image_bytes = {}
    for image in images:
        with image.asset.file.open("rb") as uploaded:
            image_bytes[str(image.asset_id)] = uploaded.read()
    version.public_snapshot = public
    version.internal_snapshot = {
        "schema": 1,
        "client": (
            {"name": quote.client.name, "contact": quote.client.contact}
            if quote.client
            else None
        ),
        "items": [
            {
                "id": str(item.pk),
                "total": str(item.total),
                "manual_price": (
                    str(item.manual_price) if item.manual_price is not None else None
                ),
                "snapshot": item.snapshot,
            }
            for item in items
        ],
        "limitations_confirmed": confirm_limitations,
        "below_cost_confirmed": confirm_below_cost,
    }
    version.content_hash = hashlib.sha256(
        json.dumps(
            public, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    version.pdf = generate_pdf(public, image_bytes=image_bytes)
    from accounts.quotas import ensure_storage

    ensure_storage(owner, len(version.pdf))
    version.published_at = now
    version.status = "sent"
    version.save()
    if quote.current_version_id:
        QuoteVersion.objects.filter(pk=quote.current_version_id).exclude(
            status="approved"
        ).update(status="superseded")
    quote.current_version = version
    quote.save(update_fields=["current_version"])
    QuoteEvent.objects.create(version=version, kind="published")
    return version, make_token(version)


@transaction.atomic
def reissue_token(*, owner, version_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(QuoteVersion, pk=version_id, quote__owner=owner)
    if (
        not version.published_at
        or version.status in {"revoked", "superseded"}
        or version.expires_at <= timezone.now()
    ):
        raise ValidationError("Esta versão não pode receber novo link.")
    version.tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    return make_token(version)


def get_token(raw):
    if len(raw) > 100:
        raise Http404
    token = get_object_or_404(
        ShareToken.objects.select_related("version__quote"),
        digest=hashlib.sha256(raw.encode()).hexdigest(),
        revoked_at__isnull=True,
        version__quote__owner__is_active=True,
    )
    from accounts.privacy import assert_not_erased

    try:
        assert_not_erased(token.version.quote.owner_id)
    except (ValidationError, OSError, ValueError):
        raise Http404
    if token.expires_at <= timezone.now() or token.version.status == "revoked":
        raise Http404
    return token


@transaction.atomic
def decide(*, raw, action, key, declaration):
    token = get_token(raw)
    owner = token.version.quote.owner
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    token = get_token(
        raw
    )  # Revalidate expiry/revocation after acquiring the mutation lock.
    version = QuoteVersion.objects.select_for_update().get(pk=token.version_id)
    quote = Quote.objects.select_for_update().get(pk=version.quote_id)
    if quote.current_version_id != version.pk:
        raise ValidationError(
            "Esta versão foi substituída. Solicite o orçamento atualizado."
        )
    if version.expires_at <= timezone.now():
        raise ValidationError("A validade desta versão terminou.")
    if action not in {"approve", "decline", "changes"}:
        raise ValidationError("Ação inválida.")
    existing = version.events.filter(key=key).first()
    if existing:
        if existing.kind != action:
            raise ValidationError("A solicitação já foi processada com outra decisão.")
        return version
    target = {"approve": "approved", "decline": "declined", "changes": "changes"}[
        action
    ]
    if version.status == target:
        return version
    if version.status != "sent":
        raise ValidationError(
            "Esta versão já recebeu uma decisão e não pode ser alterada pelo link."
        )
    if not declaration:
        raise ValidationError("Confirme que leu a versão apresentada.")
    version.status = target
    if action == "approve":
        version.accepted_at = timezone.now()
        version.approved_hash = version.content_hash
    version.save(update_fields=["status", "accepted_at", "approved_hash"])
    QuoteEvent.objects.create(
        version=version,
        kind=action,
        key=key,
        declaration="Li a versão apresentada e confirmei minha decisão.",
    )
    emit(
        owner=owner,
        kind="quote_" + target,
        object_id=version.pk,
        message=f"Orçamento {quote.number}, versão {version.number}: {version.get_status_display().lower()}.",
    )
    return version


@transaction.atomic
def revoke_links(*, owner, version_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(QuoteVersion, pk=version_id, quote__owner=owner)
    count = version.tokens.filter(revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    if count:
        QuoteEvent.objects.create(version=version, kind="revoked")
    return count
