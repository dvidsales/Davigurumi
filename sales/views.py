from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, FileResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_GET
from .models import (
    Client,
    Quote,
    QuoteVersion,
    QuoteItem,
    QuoteEvent,
    FileAsset,
    QuoteImage,
)
from .forms import (
    ClientForm,
    QuoteForm,
    QuoteItemForm,
    PublishForm,
    PortalForm,
    ImageForm,
)
from accounts.partners import search_contacts
from . import services


@never_cache
@login_required
def clients(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.owner = request.user
        try:
            with transaction.atomic():
                from accounts.quotas import ensure_capacity

                ensure_capacity(request.user, "sales.client")
                client.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("sales:clients")
    return render(
        request,
        "contact_directory.html",
        {
            "form": form,
            "heading": "Pesquisar clientes",
            "kind": "client",
            "query": request.GET.get("q", ""),
            "create_url": reverse("sales:create"),
            "page_obj": Paginator(
                __import__(
                    "accounts.partners", fromlist=["search_contacts"]
                ).search_contacts(Client, request.user, request.GET.get("q", "")),
                20,
            ).get_page(request.GET.get("page")),
        },
    )


@never_cache
@login_required
def index(request):
    return render(
        request,
        "sales/index.html",
        {
            "page_obj": Paginator(
                Quote.objects.filter(owner=request.user).select_related(
                    "client", "current_version"
                ),
                20,
            ).get_page(request.GET.get("page"))
        },
    )


@never_cache
@login_required
def create(request):
    form = QuoteForm(
        request.POST or None,
        owner=request.user,
        contact_query=request.GET.get("contact_q", ""),
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            quote = services.create_quote(
                owner=request.user,
                client_id=data["client"].pk if data["client"] else None,
                client_name=data["new_client_name"],
                client_contact=data["new_client_contact"],
                terms=data["terms"],
                delivery_date=data["delivery_date"],
                valid_days=data["valid_days"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("sales:detail", pk=quote.pk)
    return render(
        request,
        "contact_workflow.html",
        {
            "form": form,
            "contact_field": form["client"],
            "new_name": form["new_client_name"],
            "new_contact": form["new_client_contact"],
            "contact_title": "Cliente",
            "contact_query": request.GET.get("contact_q", ""),
            "directory_url": reverse("sales:clients"),
            "heading": "Novo orçamento",
            "description": "Cadastre ou escolha o cliente; depois adicione as peças, confira o preço e revise a prévia.",
        },
    )


@never_cache
@login_required
def detail(request, pk):
    quote = get_object_or_404(
        Quote.objects.select_related("client", "current_version"),
        pk=pk,
        owner=request.user,
    )
    return render(
        request,
        "sales/detail.html",
        {
            "quote": quote,
            "version": quote.versions.order_by("-number").first(),
            "workflow_step": 2,
        },
    )


@never_cache
@login_required
def item(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    form = QuoteItemForm(
        request.POST or None, owner=request.user, project_id=request.GET.get("project")
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        choices = {
            name.removeprefix("alternative_"): str(value.pk)
            for name, value in data.items()
            if name.startswith("alternative_") and value
        }
        try:
            services.add_quote_item(
                owner=request.user,
                version_id=pk,
                project_id=data["project"].pk if data["project"] else None,
                new_piece_name=data["new_piece_name"],
                quantity=data["quantity"],
                description=data["description"],
                manual_price=(
                    None
                    if data["use_calculated_price"] and data["project"]
                    else data["manual_price"]
                ),
                discount=data["discount"] / Decimal(100),
                fixed_discount=data["fixed_discount"],
                choices=choices,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(
                None, exc.messages if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            return redirect("sales:detail", pk=version.quote_id)
    return render(
        request,
        "sales/item_form.html",
        {
            "form": form,
            "heading": "Adicionar item ao orçamento",
            "workflow_step": 2,
            "projects": form.fields["project"].queryset,
            "version": version,
        },
    )


@never_cache
@login_required
def edit_item(request, pk):
    item = get_object_or_404(
        QuoteItem.objects.select_related("project_revision__project", "version"),
        pk=pk,
        version__quote__owner=request.user,
    )
    initial = {
        "project": item.project_revision.project_id,
        "quantity": item.quantity,
        "description": item.description,
        "manual_price": item.manual_price,
        "discount": Decimal(item.snapshot.get("discount", "0")) * 100,
        "fixed_discount": item.snapshot.get("fixed_discount", "0"),
    }
    if request.GET.get("project"):
        from projects.models import Project

        import uuid

        try:
            selected_id = uuid.UUID(request.GET["project"])
        except (ValueError, TypeError):
            raise Http404
        selected = get_object_or_404(Project, pk=selected_id, owner=request.user)
        initial.update(
            project=selected.pk,
            description=(selected.current_revision.description or selected.name)[:300],
            manual_price=None,
        )
    for line in item.snapshot.get("materials", []):
        if line.get("alternative"):
            initial["alternative_" + line["line"]] = line["alternative"]
    form = QuoteItemForm(
        request.POST or None,
        owner=request.user,
        project_id=initial["project"],
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        choices = {
            name.removeprefix("alternative_"): str(value.pk)
            for name, value in data.items()
            if name.startswith("alternative_") and value
        }
        try:
            services.edit_draft_item(
                owner=request.user,
                item_id=pk,
                project_id=data["project"].pk if data["project"] else None,
                new_piece_name=data["new_piece_name"],
                quantity=data["quantity"],
                description=data["description"],
                manual_price=(
                    None
                    if data["use_calculated_price"] and data["project"]
                    else data["manual_price"]
                ),
                discount=data["discount"] / Decimal(100),
                fixed_discount=data["fixed_discount"],
                choices=choices,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(
                None, exc.messages if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            return redirect("sales:detail", pk=item.version.quote_id)
    return render(
        request,
        "sales/item_form.html",
        {
            "form": form,
            "version": item.version,
            "workflow_step": 2,
            "submit_label": "Confirmar alterações",
            "heading": "Editar peça do orçamento",
            "description": "A memória de cálculo será atualizada usando a ficha atual. Versões já publicadas permanecem intactas.",
        },
    )


@never_cache
@login_required
def edit_version(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    form = QuoteForm(
        request.POST or None,
        owner=request.user,
        initial={
            "terms": version.terms,
            "delivery_date": version.delivery_date,
            "valid_days": version.valid_days,
        },
    )
    for name in ("client", "new_client_name", "new_client_contact"):
        form.fields.pop(name, None)
    if request.method == "POST" and form.is_valid():
        try:
            services.edit_draft_version(
                owner=request.user, version_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("sales:detail", pk=version.quote_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Cliente e condições",
            "version": version,
            "workflow_step": 1,
            "description": f"Cliente: {version.quote.client or 'Não informado'}. Confira as condições desta versão.",
        },
    )


@never_cache
@login_required
def publish(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    if not version.items.exists():
        messages.info(
            request, "Adicione uma peça ao orçamento antes de revisar e publicar."
        )
        return redirect("sales:item", pk=version.pk)
    form = PublishForm(request.POST or None)
    items = list(version.items.all())
    if all(item.snapshot.get("complete", False) for item in items):
        form.fields.pop("confirm_limitations")
    if all(
        item.total * (1 - Decimal(item.snapshot["fee"]))
        >= Decimal(item.snapshot["cost"])
        for item in items
    ):
        form.fields.pop("confirm_below_cost")
    if request.method == "POST" and form.is_valid():
        try:
            published, raw = services.publish(
                owner=request.user, version_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return render(
                request,
                "sales/share.html",
                {
                    "version": published,
                    "share_url": request.build_absolute_uri(
                        reverse("sales:portal", args=[raw])
                    ),
                },
            )
    preview = {
        "items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "total": str(item.total),
            }
            for item in version.items.all()
        ],
        "terms": version.terms,
        "delivery_date": version.delivery_date,
        "total": sum((item.total for item in version.items.all()), Decimal(0)),
    }
    return render(
        request,
        "sales/publish.html",
        {
            "workflow_step": 3,
            "form": form,
            "version": version,
            "public": preview,
            "images": version.images.filter(is_public=True).select_related("asset"),
        },
    )


@never_cache
@login_required
@require_POST
def new_version(request, pk):
    version = services.new_version(owner=request.user, quote_id=pk)
    return redirect("sales:detail", pk=version.quote_id)


@never_cache
@login_required
@require_POST
def remove_item(request, pk):
    item = get_object_or_404(QuoteItem, pk=pk, version__quote__owner=request.user)
    quote_id = item.version.quote_id
    try:
        services.remove_draft_item(owner=request.user, item_id=pk)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("sales:detail", pk=quote_id)


@never_cache
@login_required
@require_POST
def reissue(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    try:
        raw = services.reissue_token(owner=request.user, version_id=pk)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:detail", pk=version.quote_id)
    return render(
        request,
        "sales/share.html",
        {
            "version": version,
            "share_url": request.build_absolute_uri(
                reverse("sales:portal", args=[raw])
            ),
        },
    )


@never_cache
@login_required
def owner_pdf(request, pk):
    version = get_object_or_404(
        QuoteVersion, pk=pk, quote__owner=request.user, published_at__isnull=False
    )
    response = HttpResponse(bytes(version.pdf), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="orcamento-{version.quote.number}-v{version.number}.pdf"'
    )
    return response


@never_cache
def portal(request, raw):
    token = services.get_token(raw)
    version = token.version
    form = PortalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            version = services.decide(raw=raw, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.messages)
    elif request.method == "GET":
        cutoff = timezone.now() - timedelta(minutes=5)
        if not version.events.filter(kind="view", created_at__gte=cutoff).exists():
            QuoteEvent.objects.create(version=version, kind="view")
    can_decide = (
        version.status == "sent" and version.quote.current_version_id == version.pk
    )
    return render(
        request,
        "sales/portal.html",
        {
            "public": version.public_snapshot,
            "status": version.get_status_display(),
            "can_decide": can_decide,
            "form": form,
            "raw": raw,
        },
    )


@never_cache
def portal_pdf(request, raw):
    token = services.get_token(raw)
    response = HttpResponse(bytes(token.version.pdf), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="orcamento.pdf"'
    return response


@never_cache
@login_required
def image_upload(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    form = ImageForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        from .files import attach_image

        try:
            attach_image(owner=request.user, version_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("sales:detail", pk=version.quote_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Imagem do orçamento",
            "description": "Interna por padrão. Somente imagens explicitamente selecionadas entram no portal e no PDF.",
        },
    )


@never_cache
@login_required
def owner_image(request, pk):
    asset = get_object_or_404(FileAsset, pk=pk, owner=request.user)
    try:
        uploaded = asset.file.open("rb")
    except (OSError, ValidationError):
        return HttpResponse(
            "Imagem temporariamente indisponível. Tente novamente mais tarde.",
            status=503,
        )
    response = FileResponse(
        uploaded,
        content_type="image/png" if asset.file.name.endswith(".png") else "image/jpeg",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
def portal_image(request, raw, pk):
    token = services.get_token(raw)
    allowed = {image["id"] for image in token.version.public_snapshot.get("images", [])}
    if str(pk) not in allowed:
        from django.http import Http404

        raise Http404
    asset = get_object_or_404(FileAsset, pk=pk, owner=token.version.quote.owner)
    try:
        uploaded = asset.file.open("rb")
    except (OSError, ValidationError):
        return HttpResponse(
            "Imagem temporariamente indisponível. Tente novamente mais tarde.",
            status=503,
        )
    response = FileResponse(
        uploaded,
        content_type="image/png" if asset.file.name.endswith(".png") else "image/jpeg",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@login_required
@require_POST
@transaction.atomic
def image_action(request, pk):
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    image = get_object_or_404(
        QuoteImage.objects.select_related("version"),
        pk=pk,
        version__quote__owner=request.user,
    )
    if image.version.published_at:
        messages.error(
            request,
            "A imagem faz parte de uma versão publicada. Crie uma nova versão para mudar a seleção.",
        )
    elif request.POST.get("action") == "remove":
        image.delete()
    else:
        image.is_public = not image.is_public
        image.save(update_fields=["is_public"])
    return redirect("sales:detail", pk=image.version.quote_id)


@never_cache
@login_required
@require_POST
def revoke(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    services.revoke_links(owner=request.user, version_id=pk)
    messages.success(
        request,
        "Acesso pelos links desta versão revogado. PDF e aceite históricos foram preservados.",
    )
    return redirect("sales:detail", pk=version.quote_id)


@never_cache
@login_required
def compare(request, pk):
    from .forms import CompareForm

    quote = get_object_or_404(Quote, pk=pk, owner=request.user)
    versions = list(quote.versions.order_by("-number")[:2])
    data = request.GET or {"before": versions[-1].pk, "after": versions[0].pk}
    form = CompareForm(data, quote=quote)
    context = {"quote": quote, "form": form}
    if form.is_valid():
        before, after = form.cleaned_data["before"], form.cleaned_data["after"]
        old = {item.line_key: item for item in before.items.all()}
        new = {item.line_key: item for item in after.items.all()}
        rows = []
        for key in sorted(set(old) | set(new), key=str):
            a, b = old.get(key), new.get(key)
            changed = (
                not a
                or not b
                or (a.description, a.quantity, a.total, a.snapshot)
                != (b.description, b.quantity, b.total, b.snapshot)
            )
            rows.append(
                {
                    "before": a,
                    "after": b,
                    "status": (
                        "Adicionado"
                        if not a
                        else (
                            "Removido"
                            if not b
                            else "Alterado" if changed else "Preservado"
                        )
                    ),
                }
            )
        context.update(
            before=before,
            after=after,
            rows=rows,
            terms_changed=(before.terms, before.delivery_date, before.valid_days)
            != (after.terms, after.delivery_date, after.valid_days),
        )
    return render(request, "sales/compare.html", context)


@never_cache
@login_required
def client_history(request, pk):
    contact = get_object_or_404(Client, pk=pk, owner=request.user)
    quotes = Quote.objects.filter(owner=request.user, client=contact).select_related(
        "current_version"
    )
    from production.models import Order

    orders = Order.objects.filter(
        owner=request.user, approved_version__quote__client=contact
    ).select_related("approved_version__quote")
    return render(
        request,
        "contact_history.html",
        {"contact": contact, "kind": "client", "quotes": quotes, "orders": orders},
    )


@never_cache
@login_required
@require_GET
def piece_suggestion(request, pk):
    from projects.models import Project
    from projects.services import snapshot_project
    from pricing.domain import calculate_price

    project = get_object_or_404(
        Project.objects.select_related("current_revision"), pk=pk, owner=request.user
    )
    values = {
        "project": str(project.pk),
        "quantity": request.GET.get("quantity", "1"),
        "discount": request.GET.get("discount", "0"),
        "fixed_discount": request.GET.get("fixed_discount", "0"),
    }
    for name, value in request.GET.items():
        if name.startswith("alternative_"):
            values[name] = value
    form = QuoteItemForm(values, owner=request.user)
    if not form.is_valid():
        return JsonResponse(
            {"error": "Confira a quantidade e os descontos."}, status=400
        )
    data = form.cleaned_data
    choices = {
        name.removeprefix("alternative_"): str(value.pk)
        for name, value in data.items()
        if name.startswith("alternative_") and value
    }
    try:
        snapshot = snapshot_project(
            owner=request.user,
            revision_id=project.current_revision_id,
            quantity=data["quantity"],
            choices=choices,
        )
        result = calculate_price(
            cost=Decimal(snapshot["cost"]),
            mode=snapshot["mode"],
            percentage=Decimal(snapshot["percentage"]),
            fee=Decimal(snapshot["fee"]),
            discount=data["discount"] / Decimal(100),
            fixed_discount=data["fixed_discount"],
        )
    except (ValidationError, ValueError):
        return JsonResponse(
            {
                "error": "Não foi possível calcular com esses dados. Confira a ficha e os descontos."
            },
            status=400,
        )
    previous = (
        QuoteItem.objects.filter(
            version__quote__owner=request.user,
            project_revision__project=project,
            manual_price__isnull=False,
        )
        .order_by("-version__quote__created_at", "-version__number", "-pk")
        .first()
    )
    manual = (
        (previous.manual_price / previous.quantity * data["quantity"]).quantize(
            Decimal(".01")
        )
        if previous and not snapshot["complete"]
        else None
    )
    return JsonResponse(
        {
            "description": (project.current_revision.description or project.name)[:300],
            "calculated_price": (
                str(result.sale_price) if snapshot["complete"] else None
            ),
            "manual_price": str(manual) if manual is not None else None,
            "complete": snapshot["complete"],
            "has_alternatives": project.current_revision.materials.filter(
                alternatives__isnull=False
            ).exists(),
        }
    )


@never_cache
@login_required
@require_GET
def workflow(request, pk, step):
    from production.models import Order

    version = get_object_or_404(
        QuoteVersion.objects.select_related("quote__client"),
        pk=pk,
        quote__owner=request.user,
    )
    if step not in (1, 2, 3, 4):
        raise Http404
    if step == 1 and not version.published_at:
        return redirect("sales:edit_version", pk=pk)
    if step == 2:
        return render(
            request,
            "sales/detail.html",
            {"quote": version.quote, "version": version, "workflow_step": 2},
        )
    if step == 3 and not version.published_at and version.items.exists():
        return redirect("sales:publish", pk=pk)
    order = Order.objects.filter(
        owner=request.user, approved_version__quote=version.quote
    ).first()
    return render(
        request,
        "sales/workflow.html",
        {
            "quote": version.quote,
            "version": version,
            "workflow_step": step,
            "order": order,
        },
    )
