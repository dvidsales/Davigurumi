"""All mutations serialize by owner, then lock material/layers in stable order."""

import hashlib
import json
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import (
    Material,
    CostLayer,
    MaterialConversion,
    StockMovement,
    StockOperation,
    StockReservation,
    ReservationEvent,
)

ZERO = Decimal("0")
PRECISION = Decimal("0.000001")
LIMIT = Decimal("999999.999999")


def valid_quantity(value, *, positive=True):
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or abs(value) > LIMIT
        or value.quantize(PRECISION) != value
    ):
        raise ValidationError(
            "Quantidade inválida: use até seis casas decimais, dentro do limite suportado."
        )
    if (positive and value <= 0) or (not positive and value < 0):
        raise ValidationError("A quantidade precisa ser maior que zero.")
    return value


def to_base(material, quantity, unit=None):
    valid_quantity(quantity)
    unit = unit or material.unit
    dimensional = {
        "g": {"g": Decimal(1), "kg": Decimal(1000), "mg": Decimal(".001")},
        "m": {"m": Decimal(1), "cm": Decimal(".01"), "mm": Decimal(".001")},
        "un": {"un": Decimal(1)},
    }
    factors = dimensional[material.unit]
    if unit in factors:
        factor, version = factors[unit], None
    else:
        conversion = material.conversions.filter(name=unit).order_by("-version").first()
        if conversion is None:
            raise ValidationError(
                "Conversão não cadastrada para este material e apresentação."
            )
        factor, version = conversion.factor, conversion.version
    base = valid_quantity(quantity * factor)
    if material.unit == "un" and base != base.to_integral_value():
        raise ValidationError(
            "Este material é indivisível. A quantidade convertida precisa ser inteira."
        )
    return base, {
        "from": unit,
        "to": material.unit,
        "factor": str(factor),
        "version": version,
    }


def begin_operation(owner, key, action, payload):
    # Locking the owner's row also makes same-key concurrent requests deterministic.
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    existing = StockOperation.objects.filter(owner=owner, key=key).first()
    if existing:
        if existing.action != action or existing.payload_hash != digest:
            raise ValidationError(
                "Esta chave já foi usada em outra operação. Atualize o formulário."
            )
        return existing, True
    return (
        StockOperation.objects.create(
            owner=owner, key=key, action=action, payload_hash=digest
        ),
        False,
    )


def finish(operation, result):
    operation.result = result
    operation.save(update_fields=["result"])
    return result


@transaction.atomic
def add_conversion(*, owner, material_id, name, factor):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    material = get_object_or_404(
        Material.objects.select_for_update(), pk=material_id, owner=owner
    )
    valid_quantity(factor)
    name = name.strip()
    if not name or len(name) > 40 or name in {"g", "kg", "mg", "m", "cm", "mm", "un"}:
        raise ValidationError(
            "Use um nome de embalagem, por exemplo novelo ou pacote de 6."
        )
    previous = material.conversions.filter(name=name).order_by("-version").first()
    return MaterialConversion.objects.create(
        material=material,
        name=name,
        factor=factor,
        version=previous.version + 1 if previous else 1,
    )


@transaction.atomic
def receive_stock(
    *,
    owner,
    material_id,
    quantity,
    unit_cost,
    key,
    unit=None,
    lot="",
    reason="Entrada de estoque",
    kind="receipt",
    source_conversion=None,
):
    if kind not in {"receipt", "adjustment", "return"}:
        raise ValidationError("Tipo de entrada inválido.")
    if unit_cost is not None and (
        not isinstance(unit_cost, Decimal)
        or not unit_cost.is_finite()
        or unit_cost < 0
        or unit_cost > LIMIT
        or unit_cost.quantize(PRECISION) != unit_cost
    ):
        raise ValidationError("Custo unitário inválido.")
    op, repeated = begin_operation(
        owner,
        key,
        "receive",
        {
            "material": material_id,
            "quantity": quantity,
            "unit": unit,
            "cost": unit_cost,
            "lot": lot,
            "reason": reason,
            "kind": kind,
            "source_conversion": source_conversion,
        },
    )
    if repeated:
        return op.result
    material = get_object_or_404(
        Material.objects.select_for_update(), pk=material_id, owner=owner
    )
    base, conversion = to_base(material, quantity, unit)
    if material.physical_stock + base > LIMIT:
        raise ValidationError("O saldo ultrapassaria o limite suportado nesta versão.")
    layer = CostLayer.objects.create(
        material=material,
        original_quantity=base,
        physical=base,
        unit_cost=unit_cost,
        lot=lot,
    )
    movement = StockMovement.objects.create(
        material=material,
        layer=layer,
        quantity=base,
        unit_cost=unit_cost,
        kind=kind,
        operation=op,
        conversion_snapshot=source_conversion or conversion,
        reason=reason[:100],
    )
    return finish(
        op,
        {"layer": str(layer.pk), "movement": str(movement.pk), "quantity": str(base)},
    )


@transaction.atomic
def reserve_stock(
    *, owner, material_id, quantity, key, unit=None, reference=None, label=""
):
    op, repeated = begin_operation(
        owner,
        key,
        "reserve",
        {
            "material": material_id,
            "quantity": quantity,
            "unit": unit,
            "reference": reference,
            "label": label,
        },
    )
    if repeated:
        return op.result
    material = get_object_or_404(
        Material.objects.select_for_update(), pk=material_id, owner=owner
    )
    base, _ = to_base(material, quantity, unit)
    layers = list(material.layers.select_for_update().order_by("created_at", "id"))
    available = sum((layer.physical - layer.reserved for layer in layers), ZERO)
    if available < base:
        raise ValidationError(
            f"Estoque insuficiente. Você pediu {base} {material.unit}, mas há {available} disponíveis."
        )
    remaining, ids = base, []
    for layer in layers:
        allocated = min(remaining, layer.physical - layer.reserved)
        if allocated <= 0:
            continue
        row = StockReservation.objects.create(
            layer=layer,
            quantity=allocated,
            remaining=allocated,
            reference=reference,
            label=label[:100],
        )
        layer.reserved += allocated
        layer.save(update_fields=["reserved"])
        ReservationEvent.objects.create(
            reservation=row, operation=op, kind="reserve", quantity=allocated
        )
        ids.append(str(row.pk))
        remaining -= allocated
        if not remaining:
            break
    return finish(op, {"reservations": ids, "quantity": str(base)})


@transaction.atomic
def consume_reserved(*, owner, reservation_id, quantity, key):
    valid_quantity(quantity)
    op, repeated = begin_operation(
        owner,
        key,
        "consume_reserved",
        {"reservation": reservation_id, "quantity": quantity},
    )
    if repeated:
        return op.result
    reservation = get_object_or_404(
        StockReservation.objects.select_for_update(),
        pk=reservation_id,
        layer__material__owner=owner,
    )
    layer = CostLayer.objects.select_for_update().get(pk=reservation.layer_id)
    if quantity > reservation.remaining:
        raise ValidationError("O consumo ultrapassa a reserva remanescente.")
    if layer.material.unit == "un" and quantity != quantity.to_integral_value():
        raise ValidationError("Este material é indivisível.")
    layer.physical -= quantity
    layer.reserved -= quantity
    reservation.remaining -= quantity
    layer.save(update_fields=["physical", "reserved"])
    reservation.save(update_fields=["remaining"])
    movement = StockMovement.objects.create(
        material=layer.material,
        layer=layer,
        quantity=-quantity,
        unit_cost=layer.unit_cost,
        kind="consumption",
        operation=op,
        reason="Consumo reservado",
    )
    ReservationEvent.objects.create(
        reservation=reservation, operation=op, kind="consume", quantity=quantity
    )
    return finish(
        op,
        {
            "movement": str(movement.pk),
            "quantity": str(quantity),
            "cost": (
                str(quantity * layer.unit_cost) if layer.unit_cost is not None else None
            ),
        },
    )


@transaction.atomic
def release_reservation(*, owner, reservation_id, key):
    op, repeated = begin_operation(
        owner, key, "release", {"reservation": reservation_id}
    )
    if repeated:
        return op.result
    row = get_object_or_404(
        StockReservation.objects.select_for_update(),
        pk=reservation_id,
        layer__material__owner=owner,
    )
    layer = CostLayer.objects.select_for_update().get(pk=row.layer_id)
    released = row.remaining
    layer.reserved -= released
    row.remaining = ZERO
    layer.save(update_fields=["reserved"])
    row.save(update_fields=["remaining"])
    ReservationEvent.objects.create(
        reservation=row, operation=op, kind="release", quantity=released
    )
    return finish(op, {"released": str(released)})


@transaction.atomic
def consume_available(
    *, owner, material_id, quantity, key, reason="Consumo", kind="consumption"
):
    if kind not in {"consumption", "loss", "adjustment"} or not reason.strip():
        raise ValidationError("Informe um motivo válido.")
    op, repeated = begin_operation(
        owner,
        key,
        "consume",
        {"material": material_id, "quantity": quantity, "reason": reason, "kind": kind},
    )
    if repeated:
        return op.result
    material = get_object_or_404(
        Material.objects.select_for_update(), pk=material_id, owner=owner
    )
    base, _ = to_base(material, quantity)
    layers = list(material.layers.select_for_update().order_by("created_at", "id"))
    if sum((layer.physical - layer.reserved for layer in layers), ZERO) < base:
        raise ValidationError(
            "Estoque disponível insuficiente; reservas de outros trabalhos não podem ser consumidas."
        )
    remaining, cost, known, movements = base, ZERO, True, []
    for layer in layers:
        take = min(remaining, layer.physical - layer.reserved)
        if take <= 0:
            continue
        layer.physical -= take
        layer.save(update_fields=["physical"])
        movement = StockMovement.objects.create(
            material=material,
            layer=layer,
            quantity=-take,
            unit_cost=layer.unit_cost,
            operation=op,
            kind=kind,
            reason=reason[:100],
        )
        movements.append(str(movement.pk))
        if layer.unit_cost is None:
            known = False
        else:
            cost += take * layer.unit_cost
        remaining -= take
        if not remaining:
            break
    return finish(
        op,
        {
            "movements": movements,
            "quantity": str(base),
            "cost": str(cost) if known else None,
        },
    )


def reference_cost(material, method="average"):
    layers = [
        layer
        for layer in material.layers.all().order_by("created_at", "id")
        if layer.physical - layer.reserved > 0
    ]
    if not layers:
        return None
    if method in {"oldest", "newest"}:
        return layers[0 if method == "oldest" else -1].unit_cost
    if method != "average":
        raise ValidationError("Método de custo inválido.")
    if any(layer.unit_cost is None for layer in layers):
        return None
    total = sum((layer.physical - layer.reserved for layer in layers), ZERO)
    return (
        sum(
            ((layer.physical - layer.reserved) * layer.unit_cost for layer in layers),
            ZERO,
        )
        / total
    )
