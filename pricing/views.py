from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from .domain import calculate_price
from .forms import PricingForm

@never_cache
@login_required
def calculator(request):
    form = PricingForm(request.POST or None)
    result = None
    margin_percent = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        cost = data["materials_cost"] + data["hours"] * data["hourly_rate"] + data["additional_cost"]
        try:
            result = calculate_price(cost=cost, mode=data["mode"], percentage=data["percentage"] / Decimal(100),
                fee=data["fee"] / Decimal(100), discount=data["discount"] / Decimal(100), fixed_discount=data["fixed_discount"])
        except ValueError as exc:
            form.add_error(None, str(exc))
        if result and result.effective_margin is not None:
            margin_percent = result.effective_margin * Decimal(100)
    return render(request, "pricing/calculator.html", {"form": form, "result": result, "margin_percent": margin_percent})
