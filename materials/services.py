from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from .models import Material
from .models import StockMovement

@transaction.atomic
def create_material(*, form, owner):
    def existing_result():
        existing = Material.objects.filter(owner=owner, request_key=form.cleaned_data["request_key"]).first()
        if existing is not None:
            opening = existing.movements.first()
            same_material = all(getattr(existing, field) == form.cleaned_data[field] for field in form.Meta.fields)
            same_opening = (opening.quantity if opening else 0) == form.cleaned_data["initial_quantity"]
            same_cost = not opening or opening.unit_cost == form.cleaned_data["initial_unit_cost"]
            if not (same_material and same_opening and same_cost):
                raise ValidationError("Este formulário já foi enviado com outros valores. Abra um novo cadastro.")
        return existing

    existing = existing_result()
    if existing:
        return existing
    material = form.save(commit=False)
    material.owner = owner
    material.request_key = form.cleaned_data["request_key"]
    material.full_clean(validate_constraints=False)
    try:
        with transaction.atomic():
            material.save()
    except IntegrityError:
        existing = existing_result()
        if existing:
            return existing
        raise
    if form.cleaned_data["initial_quantity"] > 0:
        opening = StockMovement(material=material, quantity=form.cleaned_data["initial_quantity"],
                                unit_cost=form.cleaned_data["initial_unit_cost"])
        opening.full_clean()
        opening.save()
    return material
