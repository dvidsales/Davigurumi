from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from production.models import Order
from sales.models import QuoteVersion
from .models import Payment, PaymentAllocation, Refund, Receivable
from .forms import PaymentForm, RefundForm, ReceivableForm
from . import services


@never_cache
@login_required
def index(request):
    payments = Payment.objects.filter(owner=request.user).order_by(
        "-date", "-created_at"
    )
    receipts = sum((row.amount for row in payments), Decimal(0))
    refunds = sum(
        (
            row.amount
            for row in Refund.objects.filter(allocation__payment__owner=request.user)
        ),
        Decimal(0),
    )
    return render(
        request,
        "finance/index.html",
        {
            "page_obj": Paginator(payments.select_related("allocation"), 20).get_page(
                request.GET.get("page")
            ),
            "approved_quotes": QuoteVersion.objects.filter(
                quote__owner=request.user,
                status="approved",
                quote__current_version=F("pk"),
            ).select_related("quote", "quote__client")[:20],
            "receipts": receipts,
            "refunds": refunds,
            "net": receipts - refunds,
        },
    )


@never_cache
@login_required
def payment(request, pk):
    version = get_object_or_404(
        QuoteVersion, pk=pk, quote__owner=request.user, status="approved"
    )
    allocations = version.allocations.select_related("payment").prefetch_related(
        "refunds"
    )
    received = sum(
        (
            row.amount
            - sum((refund.amount for refund in row.refunds.all()), Decimal(0))
            for row in allocations
        ),
        Decimal(0),
    )
    order = Order.objects.filter(current_version=version, owner=request.user).first()
    balance = order.balance if order else max(Decimal(0), version.total - received)
    latest = allocations.order_by("-payment__date", "-payment__created_at").first()
    form = PaymentForm(
        request.POST if request.method == "POST" else None,
        initial={
            "amount": balance or None,
            "method": latest.payment.method if latest else "pix",
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.record_payment(
                owner=request.user, version_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            order = Order.objects.filter(current_version=version).first()
            return (
                redirect("production:detail", pk=order.pk)
                if order
                else redirect("sales:detail", pk=version.quote_id)
            )
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Registrar recebimento manual",
            "description": f"Saldo a receber: R$ {balance:.2f}. O saldo, a data de hoje e o meio de pagamento vêm sugeridos. Confira ou edite e confirme somente dinheiro já recebido.",
            "submit_label": "Confirmar recebimento",
        },
    )


@never_cache
@login_required
def refund(request, pk):
    allocation = get_object_or_404(
        PaymentAllocation, pk=pk, payment__owner=request.user
    )
    form = RefundForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.refund_payment(
                owner=request.user, allocation_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return (
                redirect("production:detail", pk=allocation.order_id)
                if allocation.order_id
                else redirect("finance:index")
            )
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Registrar estorno/reembolso",
            "description": "Cria uma reversão vinculada, sem apagar o recebimento original.",
        },
    )


@never_cache
@login_required
def receivable(request, pk):
    order = get_object_or_404(Order, pk=pk, owner=request.user)
    form = ReceivableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.add_receivable(
                owner=request.user, order_id=pk, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            return redirect("production:detail", pk=order.pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "heading": "Planejar sinal/parcela",
            "description": "Cobrança prevista não aumenta o caixa. Recebimentos líquidos são distribuídos por vencimento para indicar saldo/atraso.",
        },
    )


@never_cache
@login_required
@require_POST
def cancel_receivable(request, pk):
    row = get_object_or_404(Receivable, pk=pk, order__owner=request.user)
    row.cancelled = True
    row.save(update_fields=["cancelled"])
    return redirect("production:detail", pk=row.order_id)
