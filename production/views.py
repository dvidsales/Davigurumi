import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from datetime import timedelta
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
        {
            "page_obj": Paginator(orders, 20).get_page(request.GET.get("page")),
            "approved_quotes": QuoteVersion.objects.filter(
                quote__owner=request.user,
                status="approved",
                quote__current_version=F("pk"),
            )
            .exclude(quote__versions__initial_order__isnull=False)
            .select_related("quote", "quote__client")[:20],
        },
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
                owner=request.user,
                order_id=pk,
                version_id=request.POST.get("version"),
                reconciliation_reason=request.POST.get("reconciliation_reason", ""),
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
    initial = {}
    description = item.description
    if action == "produced":
        initial["quantity"] = item.quantity
        description += f" · Já produzido: {item.produced}. Sugerimos o total contratado: {item.quantity}. Confira ou edite."
    elif action == "delivery":
        available = max(0, item.produced - item.delivered)
        initial["quantity"] = available or None
        description += f" · Produzido: {item.produced} · Já entregue: {item.delivered} · Disponível para entregar: {available}."
        if not available:
            description += " Registre as peças prontas primeiro ou use Conferir e finalizar encomenda no pedido."
    form = forms[action](
        request.POST if request.method == "POST" else None, initial=initial, **kwargs
    )
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
        {
            "form": form,
            "heading": titles[action],
            "description": description,
            "submit_label": "Confirmar registro",
        },
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
            "planned_start": order.planned_start,
            "delivery_status": (
                order.delivery_status
                if order.delivery_status != "delivered"
                else "not_sent"
            ),
        },
    )
    if request.method == "POST" and form.is_valid():
        order.planned_start = form.cleaned_data["planned_start"]
        order.production_due = form.cleaned_data["production_due"]
        if order.delivery_status != "delivered":
            order.delivery_status = form.cleaned_data["delivery_status"]
        order.save(update_fields=["planned_start", "production_due", "delivery_status"])
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


@never_cache
@login_required
def expense(request, pk):
    from .forms import ExpenseForm

    order = get_object_or_404(Order, pk=pk, owner=request.user)
    form = ExpenseForm(request.POST or None, order=order)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data.copy()
        values["reverses"] = values["reverses"].pk if values["reverses"] else None
        try:
            services.record_expense(owner=request.user, order_id=pk, **values)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("production:detail", pk=pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Despesa real ou reversão",
            "description": "Registre embalagem extra, envio e outros custos reais. Não repita materiais consumidos nem mão de obra já registrada. Para corrigir, reverta o valor inteiro com motivo e registre uma nova despesa. Isso não movimenta recebimentos do cliente.",
        },
    )


@never_cache
@login_required
def recover(request, pk):
    from .models import Consumption
    from materials.forms import CompensationForm
    from materials.stock import compensate_movement

    consumption = get_object_or_404(
        Consumption.objects.select_related("item", "movement__material"),
        pk=pk,
        item__order__owner=request.user,
    )
    form = CompensationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            compensate_movement(
                owner=request.user,
                movement_id=consumption.movement_id,
                item_id=consumption.item_id,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("production:detail", pk=consumption.item.order_id)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Recuperar sobra física do pedido",
            "description": f"Material: {consumption.movement.material.name}. Informe somente sobra que voltou fisicamente ao estoque; o consumo original é preservado e seu custo líquido é reduzido pela compensação. Reservas não são recriadas.",
        },
    )


@never_cache
@login_required
def calendar(request):
    from collections import defaultdict
    from decimal import Decimal
    from django.db.models import Q
    from operations.reporting import PeriodForm

    today = timezone.localdate()
    data = request.GET.copy()
    data.setdefault("start", today.replace(day=1).isoformat())
    data.setdefault("end", (today + timedelta(days=30)).isoformat())
    form = PeriodForm(data, owner=request.user)
    context = {"form": form}
    if form.is_valid():
        start, end = form.cleaned_data["start"], form.cleaned_data["end"]
        orders = (
            Order.objects.filter(owner=request.user)
            .filter(
                Q(planned_start__range=(start, end))
                | Q(production_due__range=(start, end))
                | Q(current_version__delivery_date__range=(start, end))
            )
            .select_related("approved_version__quote", "current_version")
            .prefetch_related("items__sessions__corrections")
        )
        if form.cleaned_data["status"]:
            orders = orders.filter(status=form.cleaned_data["status"])
        else:
            orders = orders.exclude(status="cancelled")
        if form.cleaned_data["client"]:
            orders = orders.filter(
                approved_version__quote__client=form.cleaned_data["client"]
            )
        if form.cleaned_data["project"]:
            orders = orders.filter(
                current_version__items__project_revision__project=form.cleaned_data[
                    "project"
                ]
            ).distinct()
        days = defaultdict(list)
        for order in orders:
            seconds = sum(
                (
                    Decimal(item.snapshot.get("seconds", "0"))
                    for item in order.items.all()
                    if not item.retired
                ),
                Decimal(0),
            )
            worked = sum(
                (
                    session.effective_seconds
                    for item in order.items.all()
                    for session in item.sessions.all()
                    if session.ended_at
                ),
                0,
            )
            for date, label in [
                (order.planned_start, "Início planejado"),
                (order.production_due, "Prazo de produção"),
                (order.current_version.delivery_date, "Entrega/retirada"),
            ]:
                if date and start <= date <= end:
                    days[date].append(
                        {
                            "order": order,
                            "label": label,
                            "estimated_hours": seconds / 3600,
                            "worked_hours": Decimal(worked) / 3600,
                        }
                    )
        context["days"] = sorted(days.items())
        context["unplanned"] = Order.objects.filter(
            owner=request.user,
            planned_start__isnull=True,
            production_due__isnull=True,
            status__in=["waiting", "in_progress", "paused"],
        )
    return render(request, "production/calendar.html", context)


@never_cache
@login_required
def completion(request, pk):
    from django import forms as django_forms
    from django.core import signing
    from .forms import CompletionForm, CompletionItemForm

    order = get_object_or_404(
        Order.objects.select_related(
            "current_version", "approved_version__quote__client"
        ),
        pk=pk,
        owner=request.user,
    )
    items = list(order.items.filter(retired=False).order_by("pk"))
    latest = (
        order.allocations.select_related("payment")
        .order_by("-payment__date", "-payment__created_at")
        .first()
    )
    initial = {
        "state": signing.dumps(
            services.completion_state(order, items), salt="order-completion"
        ),
        "amount": order.balance or None,
        "method": latest.payment.method if latest else "pix",
        "complete": order.status != "cancelled",
    }
    form = CompletionForm(
        request.POST if request.method == "POST" else None, initial=initial
    )
    factory = django_forms.formset_factory(
        CompletionItemForm, extra=0, max_num=50, validate_max=True
    )
    rows = factory(
        request.POST if request.method == "POST" else None,
        prefix="items",
        initial=[
            {
                "item_id": item.pk,
                "produced": item.quantity,
                "delivery": item.quantity - item.delivered,
            }
            for item in items
        ],
    )
    if request.method == "POST":
        valid_form, valid_rows = form.is_valid(), rows.is_valid()
        if valid_form and valid_rows:
            data = form.cleaned_data
            try:
                state = signing.loads(
                    data["state"], salt="order-completion", max_age=86400
                )
                payment = (
                    {
                        name: data[name]
                        for name in (
                            "amount",
                            "date",
                            "method",
                            "notes",
                            "allow_credit",
                        )
                    }
                    if data["receive_payment"]
                    else None
                )
                services.confirm_completion(
                    owner=request.user,
                    order_id=pk,
                    key=data["key"],
                    state=state,
                    rows=rows.cleaned_data,
                    complete=data["complete"],
                    payment=payment,
                )
            except signing.BadSignature:
                form.add_error(
                    None,
                    "Esta revisão expirou ou foi alterada. Abra novamente pelo pedido.",
                )
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                messages.success(
                    request,
                    "Dados confirmados. Produção, entrega e recebimento foram registrados conforme sua revisão.",
                )
                return redirect("production:detail", pk=pk)
    return render(
        request,
        "production/completion.html",
        {"order": order, "form": form, "rows": rows, "item_rows": zip(items, rows)},
    )
