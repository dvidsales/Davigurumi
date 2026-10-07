from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .models import Notification, NotificationPreference


class PreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ("email_enabled",)


@never_cache
@login_required
def index(request):
    preference, _ = NotificationPreference.objects.get_or_create(owner=request.user)
    form = PreferenceForm(request.POST or None, instance=preference)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("operations:index")
    return render(
        request,
        "operations/index.html",
        {
            "form": form,
            "page_obj": Paginator(
                Notification.objects.filter(owner=request.user), 20
            ).get_page(request.GET.get("page")),
        },
    )


@never_cache
@login_required
@require_POST
def read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, owner=request.user)
    notification.read_at = timezone.now()
    notification.save(update_fields=["read_at"])
    return redirect("operations:index")


@never_cache
@login_required
def reports(request):
    from django.utils import timezone
    from production.models import Order
    from .reporting import PeriodForm, cash_period, replenishment

    today = timezone.localdate()
    data = request.GET or {
        "start": today.replace(day=1).isoformat(),
        "end": today.isoformat(),
    }
    form = PeriodForm(data)
    context = {"form": form, "shortages": replenishment(request.user)}
    if form.is_valid():
        start = form.cleaned_data["start"]
        end = form.cleaned_data["end"]
        orders = (
            Order.objects.filter(
                owner=request.user, created_at__date__range=(start, end)
            )
            .select_related("current_version", "approved_version__quote__client")
            .prefetch_related("allocations__refunds")
        )
        context.update(cash=cash_period(request.user, start, end), orders=orders)
        if request.GET.get("export") == "csv":
            import csv
            from io import StringIO
            from portability.tables import safe_cell
            from portability.views import download

            output = StringIO()
            writer = csv.writer(output, delimiter=";")
            writer.writerow(
                [
                    "pedido",
                    "cliente",
                    "criacao",
                    "producao",
                    "entrega",
                    "total_atual",
                    "recebido_liquido_historico",
                    "saldo_atual",
                    "credito_atual",
                ]
            )
            for order in orders:
                client = order.approved_version.quote.client
                writer.writerow(
                    [
                        str(order.pk),
                        safe_cell(client.name) if client else "",
                        order.created_at.isoformat(),
                        order.get_status_display(),
                        order.get_delivery_status_display(),
                        str(order.total),
                        str(order.net_received),
                        str(order.balance),
                        str(order.credit),
                    ]
                )
            return download(
                "\ufeff" + output.getvalue(), "text/csv; charset=utf-8", "pedidos.csv"
            )
    return render(request, "operations/reports.html", context)
