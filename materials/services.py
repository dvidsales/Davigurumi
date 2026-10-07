from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from .models import Material, CostLayer
from .models import StockMovement


@transaction.atomic
def create_material(*, form, owner):
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update().get(pk=owner.pk)

    def existing_result():
        existing = Material.objects.filter(
            owner=owner, request_key=form.cleaned_data["request_key"]
        ).first()
        if existing is not None:
            opening = existing.movements.filter(kind="opening").first()
            same_material = all(
                getattr(existing, field) == form.cleaned_data[field]
                for field in form.Meta.fields
            )
            same_opening = (opening.quantity if opening else 0) == form.cleaned_data[
                "initial_quantity"
            ]
            same_cost = (
                not opening
                or opening.unit_cost == form.cleaned_data["initial_unit_cost"]
            )
            if not (same_material and same_opening and same_cost):
                raise ValidationError(
                    "Este formulário já foi enviado com outros valores. Abra um novo cadastro."
                )
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
        layer = CostLayer.objects.create(
            material=material,
            original_quantity=form.cleaned_data["initial_quantity"],
            physical=form.cleaned_data["initial_quantity"],
            unit_cost=form.cleaned_data["initial_unit_cost"],
        )
        opening = StockMovement(
            material=material,
            quantity=form.cleaned_data["initial_quantity"],
            unit_cost=form.cleaned_data["initial_unit_cost"],
            layer=layer,
        )
        opening.full_clean()
        opening.save()
    return material


@transaction.atomic
def archive_material(*, owner, material_id, archived, reason, key):
    from django.shortcuts import get_object_or_404
    from .stock import begin_operation, finish
    from operations.models import AuditEvent

    if not isinstance(archived, bool) or not reason.strip() or len(reason) > 200:
        raise ValidationError("Informe a operação e um motivo de até 200 caracteres.")
    op, repeated = begin_operation(
        owner,
        key,
        "material_archive",
        {"material": material_id, "archived": archived, "reason": reason},
    )
    if repeated:
        return op.result
    material = get_object_or_404(
        Material.objects.select_for_update(), pk=material_id, owner=owner
    )
    if material.is_archived != archived:
        material.is_archived = archived
        material.save(update_fields=["is_archived"])
        AuditEvent.objects.create(
            owner=owner,
            action="material_archived" if archived else "material_restored",
            object_id=material.pk,
            reason=reason,
        )
    return finish(op, {"material": str(material.pk), "archived": archived})
