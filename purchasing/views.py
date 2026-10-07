from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .models import Purchase, PurchaseItem, Supplier
from .forms import PurchaseForm, SupplierForm, ItemForm, ReceiveForm
from . import services


@never_cache
@login_required
def index(request):
    return render(
        request,
        "purchasing/index.html",
        {
            "page_obj": Paginator(
                Purchase.objects.filter(owner=request.user).select_related("supplier"),
                20,
            ).get_page(request.GET.get("page"))
        },
    )


@never_cache
@login_required
def create(request):
    form = PurchaseForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        purchase = form.save(commit=False)
        purchase.owner = request.user
        purchase.save()
        return redirect("purchasing:detail", pk=purchase.pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Nova compra",
            "description": "Criar rascunho não altera estoque. Adicione itens, confirme e registre o recebimento real.",
        },
    )


@never_cache
@login_required
def suppliers(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save(commit=False)
        supplier.owner = request.user
        supplier.save()
        return redirect("purchasing:suppliers")
    return render(
        request,
        "purchasing/suppliers.html",
        {"form": form, "suppliers": Supplier.objects.filter(owner=request.user)},
    )


@never_cache
@login_required
def detail(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.prefetch_related("items__material", "receipts"),
        pk=pk,
        owner=request.user,
    )
    return render(request, "purchasing/detail.html", {"purchase": purchase})


@never_cache
@login_required
def item(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk, owner=request.user)
    form = ItemForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            services.add_item(
                owner=request.user,
                purchase_id=pk,
                material_id=data["material"].pk,
                quantity=data["quantity"],
                unit_price=data["unit_price"],
                unit=data["unit"] or None,
                lot=data["lot"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("purchasing:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Adicionar item à compra",
            "description": "O preço informado corresponde à unidade/embalagem comprada.",
        },
    )


@never_cache
@login_required
@require_POST
def action(request, pk):
    get_object_or_404(Purchase, pk=pk, owner=request.user)
    try:
        choice = request.POST.get("action")
        if choice == "confirm":
            services.confirm_purchase(owner=request.user, purchase_id=pk)
        elif choice == "cancel":
            services.cancel_purchase(owner=request.user, purchase_id=pk)
        elif choice == "repeat":
            new = services.repeat_purchase(
                owner=request.user, purchase_id=pk, date=timezone.localdate()
            )
            return redirect("purchasing:detail", pk=new.pk)
        else:
            raise ValidationError("Ação inválida.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("purchasing:detail", pk=pk)


@never_cache
@login_required
def receive(request, pk):
    item = get_object_or_404(
        PurchaseItem.objects.select_related("purchase", "material"),
        pk=pk,
        purchase__owner=request.user,
    )
    form = ReceiveForm(request.POST or None, initial={"quantity": item.remaining})
    if request.method == "POST" and form.is_valid():
        try:
            services.receive_purchase(
                owner=request.user,
                purchase_id=item.purchase_id,
                quantities={pk: form.cleaned_data["quantity"]},
                key=form.cleaned_data["key"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            messages.success(
                request,
                "Recebimento registrado; estoque e camada de custo atualizados.",
            )
            return redirect("purchasing:detail", pk=item.purchase_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": f"Receber {item.material.name}",
            "description": f"Informe somente o que já recebeu, em {item.material.unit}. Restante: {item.remaining}.",
        },
    )


@never_cache
@login_required
def edit(request, pk):
    from django.contrib.auth import get_user_model
    from django.db import transaction

    purchase = get_object_or_404(Purchase, pk=pk, owner=request.user)
    form = PurchaseForm(request.POST or None, instance=purchase, owner=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            current = Purchase.objects.select_for_update().get(pk=pk)
            if current.status != "draft":
                form.add_error(
                    None,
                    "A compra já foi confirmada. Reabra a página para consultar o histórico.",
                )
            else:
                form.save()
                return redirect("purchasing:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {"form": form, "heading": "Editar rascunho da compra"},
    )


@never_cache
@login_required
def edit_item(request, pk):
    row = get_object_or_404(PurchaseItem, pk=pk, purchase__owner=request.user)
    initial = {
        field: getattr(row, field)
        for field in ("material", "quantity", "unit", "unit_price", "lot")
    }
    form = ItemForm(request.POST or None, initial=initial, owner=request.user)
    if request.method == "POST":
        try:
            if request.POST.get("action") == "remove":
                services.remove_item(owner=request.user, item_id=pk)
            elif form.is_valid():
                values = form.cleaned_data.copy()
                values["material_id"] = values.pop("material").pk
                services.edit_item(owner=request.user, item_id=pk, **values)
            else:
                return render(
                    request,
                    "generic_form.html",
                    {"form": form, "heading": "Editar item da compra"},
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("purchasing:detail", pk=row.purchase_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Editar item da compra",
            "remove_allowed": row.purchase.status == "draft",
        },
    )


@never_cache
@login_required
def allocation(request, pk):
    from .forms import AllocationForm

    purchase = get_object_or_404(Purchase, pk=pk, owner=request.user)
    if purchase.status != "draft":
        return redirect("purchasing:detail", pk=pk)
    form = AllocationForm(request.POST or None, purchase=purchase)
    if request.method == "POST" and form.is_valid():
        try:
            services.confirm_purchase(
                owner=request.user,
                purchase_id=pk,
                manual_allocations=form.allocations(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("purchasing:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Revisar rateio e confirmar compra",
            "description": f"Total da compra: R$ {purchase.total:.2f}. No método manual, informe o custo final completo por item, incluindo sua parte do frete e desconto. No proporcional, os valores manuais são ignorados. A confirmação congela os custos antes do recebimento.",
        },
    )
