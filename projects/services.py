from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from materials.models import Material
from materials.stock import to_base, reference_cost, valid_quantity
from pricing.domain import calculate_price
from .models import Project, ProjectRevision, ProjectMaterial, MaterialAlternative


@transaction.atomic
def create_project(
    *,
    owner,
    name,
    description="",
    technique="",
    base_quantity=1,
    estimated_seconds=0,
    hourly_rate=Decimal(0),
    additional_cost=Decimal(0),
    mode="markup",
    percentage=Decimal(".5"),
    fee=Decimal(0),
    notes="",
    reference_policy="available",
    quick_entry=False,
):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    calculate_price(cost=Decimal(0), mode=mode, percentage=percentage, fee=fee)
    from accounts.quotas import ensure_capacity

    ensure_capacity(owner, "projects.project")
    ensure_capacity(owner, "projects.projectrevision")
    project = Project.objects.create(owner=owner, name=name, notes=notes)
    revision = ProjectRevision(
        project=project,
        number=1,
        name=name,
        description=description,
        technique=technique,
        base_quantity=base_quantity,
        estimated_seconds=estimated_seconds,
        hourly_rate=hourly_rate,
        reference_policy=reference_policy,
        quick_entry=quick_entry,
        additional_cost=additional_cost,
        mode=mode,
        percentage=percentage,
        fee=fee,
    )
    revision.full_clean()
    revision.save()
    project.current_revision = revision
    project.save(update_fields=["current_revision"])
    return project


def clone_revision(project):
    from accounts.quotas import ensure_capacity

    ensure_capacity(project.owner, "projects.projectrevision")
    current = project.current_revision
    if current.materials.count() > 100:
        raise ValidationError("Limite de 100 materiais por ficha.")
    values = {
        field: getattr(current, field)
        for field in (
            "quick_entry",
            "name",
            "description",
            "technique",
            "base_quantity",
            "estimated_seconds",
            "hourly_rate",
            "reference_policy",
            "additional_cost",
            "mode",
            "percentage",
            "fee",
        )
    }
    revision = ProjectRevision.objects.create(
        project=project, number=current.number + 1, **values
    )
    mapping = {}
    for old in current.materials.all():
        new = ProjectMaterial.objects.create(
            revision=revision,
            material=old.material,
            quantity=old.quantity,
            unit=old.unit,
            base_quantity=old.base_quantity,
            conversion_snapshot=old.conversion_snapshot,
            manual_unit_cost=old.manual_unit_cost,
        )
        mapping[old.pk] = new
        for alternative in old.alternatives.all():
            MaterialAlternative.objects.create(
                line=new,
                material=alternative.material,
                base_quantity=alternative.base_quantity,
                note=alternative.note,
            )
    project.current_revision = revision
    project.save(update_fields=["current_revision"])
    return revision, mapping


@transaction.atomic
def add_material(
    *, owner, project_id, material_id, quantity, unit=None, manual_unit_cost=None
):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    project = get_object_or_404(
        Project.objects.select_for_update(), pk=project_id, owner=owner
    )
    material = get_object_or_404(
        Material, pk=material_id, owner=owner, is_archived=False
    )
    if project.current_revision.materials.count() >= 100:
        raise ValidationError("Limite de 100 materiais por ficha.")
    base, snapshot = to_base(material, quantity, unit)
    revision, _ = clone_revision(project)
    line = ProjectMaterial(
        revision=revision,
        material=material,
        quantity=quantity,
        unit=unit or material.unit,
        base_quantity=base,
        conversion_snapshot=snapshot,
        manual_unit_cost=manual_unit_cost,
    )
    line.full_clean()
    line.save()
    return line


@transaction.atomic
def add_alternative(*, owner, line_id, material_id, quantity, note=""):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    old = get_object_or_404(
        ProjectMaterial.objects.select_related("revision__project"),
        pk=line_id,
        revision__project__owner=owner,
    )
    project = Project.objects.select_for_update().get(pk=old.revision.project_id)
    if old.revision_id != project.current_revision_id:
        raise ValidationError(
            "A ficha mudou. Abra a revisão atual antes de adicionar alternativa."
        )
    material = get_object_or_404(
        Material, pk=material_id, owner=owner, is_archived=False
    )
    base, _ = to_base(material, quantity)
    _, mapping = clone_revision(project)
    return MaterialAlternative.objects.create(
        line=mapping[old.pk], material=material, base_quantity=base, note=note
    )


def snapshot_project(*, owner, revision_id, quantity, choices=None):
    revision = get_object_or_404(
        ProjectRevision.objects.select_related("project"),
        pk=revision_id,
        project__owner=owner,
    )
    if not isinstance(quantity, int) or quantity <= 0 or quantity > 10000:
        raise ValidationError("Informe de 1 a 10000 unidades produzidas.")
    factor = Decimal(quantity) / revision.base_quantity
    choices = choices or {}
    lines = []
    materials_cost = Decimal(0)
    complete = True
    for line in revision.materials.select_related("material").all():
        material = line.material
        needed = line.base_quantity * factor
        manual = line.manual_unit_cost
        alternative_id = choices.get(str(line.pk))
        if alternative_id:
            alternative = get_object_or_404(
                MaterialAlternative.objects.select_related("material"),
                pk=alternative_id,
                line=line,
            )
            material = alternative.material
            needed = alternative.base_quantity * factor
            manual = None
        if material.owner_id != owner.pk:
            raise ValidationError("Material não pertence ao proprietário do projeto.")
        valid_quantity(needed)
        if material.unit == "un" and needed != needed.to_integral_value():
            raise ValidationError(
                f"A escala usa uma fração de unidade para {material.name}. Ajuste a ficha ou a quantidade produzida."
            )
        if revision.reference_policy == "manual":
            cost = manual
        elif revision.reference_policy == "latest":
            layer = material.layers.order_by("-created_at", "-id").first()
            cost = layer.unit_cost if layer else None
        else:
            cost = reference_cost(material)
        manual_reference = (
            revision.reference_policy == "manual" or cost is None and manual is not None
        )
        if cost is None and revision.reference_policy != "manual":
            cost = manual
        if cost is None:
            complete = False
        else:
            materials_cost += needed * cost
        lines.append(
            {
                "line": str(line.pk),
                "material": str(material.pk),
                "name": material.name,
                "quantity": str(needed),
                "unit": material.unit,
                "unit_cost": str(cost) if cost is not None else None,
                "manual_reference": manual_reference,
                "conversion": line.conversion_snapshot,
                "alternative": str(alternative_id) if alternative_id else None,
            }
        )
    seconds = Decimal(revision.estimated_seconds) * factor
    labor = seconds / Decimal(3600) * revision.hourly_rate
    additional = revision.additional_cost * factor
    cost = materials_cost + labor + additional
    if revision.quick_entry and not lines and labor == 0 and additional == 0:
        complete = False
    result = calculate_price(
        cost=cost, mode=revision.mode, percentage=revision.percentage, fee=revision.fee
    )
    return {
        "schema": 1,
        "formula": "prd59-v1",
        "reference_policy": revision.reference_policy,
        "project": str(revision.project_id),
        "revision": str(revision.pk),
        "revision_number": revision.number,
        "name": revision.name,
        "description": revision.description,
        "technique": revision.technique,
        "quantity": quantity,
        "materials": lines,
        "seconds": str(seconds),
        "hourly_rate": str(revision.hourly_rate),
        "additional_cost": str(additional),
        "cost": str(cost),
        "mode": revision.mode,
        "percentage": str(revision.percentage),
        "fee": str(revision.fee),
        "calculated_price": str(result.sale_price),
        "complete": complete,
    }


@transaction.atomic
def edit_project(*, owner, project_id, **values):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    project = get_object_or_404(
        Project.objects.select_for_update(), pk=project_id, owner=owner
    )
    calculate_price(
        cost=Decimal(0),
        mode=values["mode"],
        percentage=values["percentage"],
        fee=values["fee"],
    )
    revision, _ = clone_revision(project)
    for field in (
        "name",
        "description",
        "technique",
        "base_quantity",
        "estimated_seconds",
        "hourly_rate",
        "additional_cost",
        "mode",
        "percentage",
        "fee",
    ):
        setattr(revision, field, values[field])
    revision.reference_policy = values.get(
        "reference_policy", revision.reference_policy
    )
    revision.full_clean()
    revision.save()
    project.name = values["name"]
    project.notes = values.get("notes", "")
    project.save(update_fields=["name", "notes"])
    return revision


@transaction.atomic
def edit_line(
    *,
    owner,
    line_id,
    material_id=None,
    quantity=None,
    unit=None,
    manual_unit_cost=None,
    remove=False,
):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    old = get_object_or_404(
        ProjectMaterial.objects.select_related("revision__project"),
        pk=line_id,
        revision__project__owner=owner,
    )
    project = Project.objects.select_for_update().get(pk=old.revision.project_id)
    if old.revision_id != project.current_revision_id:
        raise ValidationError("A ficha mudou. Abra a revisão atual antes de editar.")
    _, mapping = clone_revision(project)
    line = mapping[old.pk]
    if remove:
        line.alternatives.all().delete()
        line.delete()
        return project
    material = get_object_or_404(
        Material, pk=material_id, owner=owner, is_archived=False
    )
    base, snapshot = to_base(material, quantity, unit)
    line.material = material
    line.quantity = quantity
    line.unit = unit or material.unit
    line.base_quantity = base
    line.conversion_snapshot = snapshot
    line.manual_unit_cost = manual_unit_cost
    line.full_clean()
    line.save()
    return project
