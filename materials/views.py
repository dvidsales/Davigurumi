import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .forms import MaterialForm, StockActionForm, ConversionForm, ReservationActionForm
from .models import Material, StockReservation
from . import stock
from .services import create_material


@never_cache
@login_required
def index(request):
    query = request.GET.get("q", "").strip()[:160]
    materials = Material.objects.filter(owner=request.user).prefetch_related(
        "movements", "layers"
    )
    state = request.GET.get("state", "active")
    if state == "archived":
        materials = materials.filter(is_archived=True)
    elif state != "all":
        state = "active"
        materials = materials.filter(is_archived=False)
    if query:
        materials = materials.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(color__icontains=query)
        )
    return render(
        request,
        "materials/index.html",
        {
            "page_obj": Paginator(materials, 20).get_page(request.GET.get("page")),
            "query": query,
            "state": state,
        },
    )


@never_cache
@login_required
def create(request):
    form = MaterialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            material = create_material(form=form, owner=request.user)
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            messages.success(
                request,
                "Material cadastrado. O histórico de estoque está disponível abaixo.",
            )
            return redirect("materials:detail", pk=material.pk)
    return render(request, "materials/form.html", {"form": form})


@never_cache
@login_required
def detail(request, pk):
    material = get_object_or_404(
        Material.objects.prefetch_related("movements", "layers", "conversions"),
        pk=pk,
        owner=request.user,
    )
    return render(
        request,
        "materials/detail.html",
        {
            "material": material,
            "archive_key": uuid.uuid4(),
            "reservations": StockReservation.objects.filter(
                layer__material=material, remaining__gt=0
            ).select_related("layer"),
            "reference_cost": stock.reference_cost(material),
        },
    )


@never_cache
@login_required
def stock_action(request, pk):
    material = get_object_or_404(Material, pk=pk, owner=request.user)
    form = StockActionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if data["action"] == "receive":
                stock.receive_stock(
                    owner=request.user,
                    material_id=pk,
                    quantity=data["quantity"],
                    unit=data["unit"] or None,
                    unit_cost=data["unit_cost"],
                    lot=data["lot"],
                    reason=data["reason"],
                    key=data["request_key"],
                )
            elif data["action"] == "reserve":
                stock.reserve_stock(
                    owner=request.user,
                    material_id=pk,
                    quantity=data["quantity"],
                    unit=data["unit"] or None,
                    label=data["reason"],
                    key=data["request_key"],
                )
            else:
                if data["unit"] and data["unit"] != material.unit:
                    raise ValidationError(
                        "Para saída, informe a quantidade na unidade base."
                    )
                stock.consume_available(
                    owner=request.user,
                    material_id=pk,
                    quantity=data["quantity"],
                    key=data["request_key"],
                    reason=data["reason"],
                    kind="loss" if data["action"] == "loss" else "consumption",
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Operação registrada no histórico.")
            return redirect("materials:detail", pk=pk)
    return render(
        request,
        "materials/action.html",
        {"material": material, "form": form, "heading": "Movimentar estoque"},
    )


@never_cache
@login_required
def conversion(request, pk):
    material = get_object_or_404(Material, pk=pk, owner=request.user)
    form = ConversionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            stock.add_conversion(
                owner=request.user, material_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request, "Conversão cadastrada. O histórico mantém o fator original."
            )
            return redirect("materials:detail", pk=pk)
    return render(
        request,
        "materials/action.html",
        {"material": material, "form": form, "heading": "Cadastrar conversão"},
    )


@never_cache
@login_required
def reservation_action(request, pk):
    reservation = get_object_or_404(
        StockReservation.objects.select_related("layer__material"),
        pk=pk,
        layer__material__owner=request.user,
    )
    form = ReservationActionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "consume":
                if reservation.reference is not None:
                    raise ValidationError(
                        "Esta reserva pertence a um pedido. Registre o consumo pela tela do item em Pedidos e produção."
                    )
                stock.consume_reserved(
                    owner=request.user,
                    reservation_id=pk,
                    quantity=form.cleaned_data["quantity"],
                    key=form.cleaned_data["request_key"],
                )
            else:
                stock.release_reservation(
                    owner=request.user,
                    reservation_id=pk,
                    key=form.cleaned_data["request_key"],
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request, "Reserva atualizada; consumo e liberação estão registrados."
            )
            return redirect("materials:detail", pk=reservation.layer.material_id)
    return render(
        request,
        "materials/action.html",
        {
            "material": reservation.layer.material,
            "form": form,
            "heading": "Usar ou liberar reserva",
        },
    )


@never_cache
@login_required
def edit(request, pk):
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from .forms import MaterialEditForm

    material = get_object_or_404(Material, pk=pk, owner=request.user)
    form = MaterialEditForm(request.POST or None, instance=material)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            edited = form.save(commit=False)
            edited.save(update_fields=list(form.Meta.fields))
        return redirect("materials:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Editar cadastro do material",
            "description": "Não altera o histórico nem os custos de entradas anteriores.",
        },
    )


@never_cache
@login_required
@require_POST
def archive(request, pk):
    from .services import archive_material

    get_object_or_404(Material, pk=pk, owner=request.user)
    try:
        action = request.POST.get("action")
        if action not in {"archive", "restore"}:
            raise ValidationError("Operação inválida.")
        archive_material(
            owner=request.user,
            material_id=pk,
            archived=action == "archive",
            reason=request.POST.get("reason", ""),
            key=uuid.UUID(request.POST.get("key", "")),
        )
    except (ValidationError, ValueError) as exc:
        messages.error(
            request,
            (
                " ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else "Formulário inválido. Atualize a página."
            ),
        )
    return redirect("materials:detail", pk=pk)


@never_cache
@login_required
def compensation(request, pk):
    from .models import StockMovement
    from .forms import CompensationForm

    movement = get_object_or_404(
        StockMovement.objects.select_related("material"),
        pk=pk,
        material__owner=request.user,
    )
    form = CompensationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            stock.compensate_movement(
                owner=request.user, movement_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("materials:detail", pk=movement.material_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Compensar movimento de estoque",
            "description": f"Origem: {movement.quantity} {movement.material.unit}. A recuperação devolve sobra física com custo histórico; a devolução de entrada exige saldo livre da camada original. Reservas não são refeitas e o original permanece no histórico. Consumos de pedido são tratados na tela do pedido.",
        },
    )
