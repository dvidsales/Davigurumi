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
    from .reporting import (
        PeriodForm,
        cash_period,
        replenishment,
        export_order_report,
        below_minimum,
    )

    today = timezone.localdate()
    data = request.GET.copy()
    data.setdefault("start", today.replace(day=1).isoformat())
    data.setdefault("end", today.isoformat())
    form = PeriodForm(data, owner=request.user)
    context = {
        "form": form,
        "shortages": replenishment(request.user),
        "below_minimum": below_minimum(request.user),
    }
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
        if form.cleaned_data["status"]:
            orders = orders.filter(status=form.cleaned_data["status"])
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
        context.update(cash=cash_period(request.user, start, end), orders=orders)
        if request.GET.get("export") in {"csv", "xlsx"}:
            return export_order_report(orders, request.GET["export"])
    return render(request, "operations/reports.html", context)
