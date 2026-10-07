import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from materials.models import StockReservation
from sales.models import QuoteVersion
from finance.services import installment_balances
from .models import Order, OrderItem, ProductionSession
from .forms import (
    ConsumeForm,
    ManualTimeForm,
    ProducedForm,
    DeliveryForm,
    CorrectionForm,
    OrderSettingsForm,
)
from . import services


def error_message(request, exc):
    messages.error(request, " ".join(exc.messages))


@never_cache
@login_required
def index(request):
    orders = Order.objects.filter(owner=request.user).select_related(
        "approved_version__quote", "current_version"
    )
    return render(
        request,
        "production/index.html",
        {"page_obj": Paginator(orders, 20).get_page(request.GET.get("page"))},
    )


@never_cache
@login_required
@require_POST
def convert(request, pk):
    version = get_object_or_404(QuoteVersion, pk=pk, quote__owner=request.user)
    try:
        order = services.create_order(owner=request.user, version_id=pk)
    except ValidationError as exc:
        error_message(request, exc)
        return redirect("sales:detail", pk=version.quote_id)
    return redirect("production:detail", pk=order.pk)


@never_cache
@login_required
def detail(request, pk):
    from .costs import cost_summary

    order = get_object_or_404(
        Order.objects.select_related(
            "current_version", "approved_version__quote"
        ).prefetch_related(
            "items__sessions", "allocations__payment", "allocations__refunds"
        ),
        pk=pk,
        owner=request.user,
    )
    return render(
        request,
        "production/detail.html",
        {
            "costs": cost_summary(order),
            "order": order,
            "key": uuid.uuid4(),
            "now": timezone.now(),
            "active": ProductionSession.objects.filter(
                owner=request.user, ended_at__isnull=True
            )
            .select_related("item")
            .first(),
            "installments": installment_balances(order),
            "amendments": QuoteVersion.objects.filter(
                quote=order.approved_version.quote,
                amends_version=order.current_version,
                status="approved",
            ),
            "reservations": StockReservation.objects.filter(
                reference__in=order.items.values_list("pk", flat=True), remaining__gt=0
            ).select_related("layer__material"),
        },
    )


@never_cache
@login_required
@require_POST
def action(request, pk):
    order = get_object_or_404(Order, pk=pk, owner=request.user)
    try:
        choice = request.POST.get("action")
        if choice == "reserve":
            services.reserve_order(
                owner=request.user,
                order_id=pk,
                key=uuid.UUID(request.POST.get("key", "")),
            )
        elif choice in {"completed", "cancelled", "waiting"}:
            services.close_order(
                owner=request.user,
                order_id=pk,
                status=choice,
                reason=request.POST.get("reason", ""),
            )
        elif choice == "amendment":
            services.apply_amendment(
                owner=request.user, order_id=pk, version_id=request.POST.get("version")
            )
        else:
            raise ValidationError("Ação inválida.")
    except (ValidationError, ValueError) as exc:
        messages.error(
            request,
            (
                " ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else "Formulário inválido. Atualize a página."
            ),
        )
    return redirect("production:detail", pk=order.pk)


@never_cache
@login_required
def item_action(request, pk, action):
    item = get_object_or_404(
        OrderItem.objects.select_related("order"), pk=pk, order__owner=request.user
    )
    forms = {
        "consume": ConsumeForm,
        "manual_time": ManualTimeForm,
        "produced": ProducedForm,
        "delivery": DeliveryForm,
    }
    titles = {
        "consume": "Registrar consumo real",
        "manual_time": "Registrar tempo manual",
        "produced": "Registrar quantidade produzida",
        "delivery": "Registrar entrega parcial/total",
    }
    if action not in forms:
        from django.http import Http404

        raise Http404
    kwargs = {"owner": request.user, "item": item} if action == "consume" else {}
    form = forms[action](request.POST or None, **kwargs)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if action == "consume":
                services.consume_item(
                    owner=request.user,
                    item_id=pk,
                    material_id=data["material"].pk,
                    quantity=data["quantity"],
                    key=data["key"],
                    reservation_id=(
                        data["reservation"].pk if data["reservation"] else None
                    ),
                )
            elif action == "manual_time":
                services.manual_time(
                    owner=request.user,
                    item_id=pk,
                    seconds=data["minutes"] * 60,
                    ended_at=data["ended_at"],
                )
            elif action == "produced":
                services.record_produced(
                    owner=request.user, item_id=pk, quantity=data["quantity"]
                )
            elif action == "delivery":
                services.deliver_item(owner=request.user, item_id=pk, **data)
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("production:detail", pk=item.order_id)
    return render(
        request,
        "generic_form.html",
        {"form": form, "heading": titles[action], "description": item.description},
    )


@never_cache
@login_required
@require_POST
def start(request, pk):
    item = get_object_or_404(OrderItem, pk=pk, order__owner=request.user)
    try:
        services.start_session(owner=request.user, item_id=pk)
    except ValidationError as exc:
        error_message(request, exc)
    return redirect("production:detail", pk=item.order_id)


@never_cache
@login_required
@require_POST
def stop(request, pk):
    session = services.stop_session(owner=request.user, session_id=pk)
    return redirect("production:detail", pk=session.item.order_id)


@never_cache
@login_required
def correction(request, pk):
    session = get_object_or_404(
        ProductionSession, pk=pk, owner=request.user, ended_at__isnull=False
    )
    form = CorrectionForm(
        request.POST or None, initial={"minutes": session.effective_seconds // 60}
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.correct_time(
                owner=request.user,
                session_id=pk,
                seconds=form.cleaned_data["minutes"] * 60,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("production:detail", pk=session.item.order_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Corrigir duração",
            "description": "O registro original será preservado, com correção e motivo anexados.",
        },
    )


@never_cache
@login_required
def settings(request, pk):
    order = get_object_or_404(Order, pk=pk, owner=request.user)
    form = OrderSettingsForm(
        request.POST or None,
        initial={
            "production_due": order.production_due,
            "delivery_status": (
                order.delivery_status
                if order.delivery_status != "delivered"
                else "not_sent"
            ),
        },
    )
    if request.method == "POST" and form.is_valid():
        order.production_due = form.cleaned_data["production_due"]
        if order.delivery_status != "delivered":
            order.delivery_status = form.cleaned_data["delivery_status"]
        order.save(update_fields=["production_due", "delivery_status"])
        return redirect("production:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Prazo e modalidade de entrega",
            "description": "A entrega final é registrada por quantidades, separada da situação da produção.",
        },
    )
