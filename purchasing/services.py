import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from materials.models import Material, StockMovement
from materials.stock import (
    begin_operation,
    finish,
    receive_stock,
    to_base,
    valid_quantity,
)
from .models import Purchase, PurchaseItem, Receipt, ReceiptLine

CENT = Decimal(".01")


def distribute(amount, weights):
    """Largest remainder distribution of exact integer cents; deterministic ties."""
    if amount == 0:
        return [Decimal(0) for _ in weights]
    total = sum(weights, Decimal(0))
    if total <= 0:
        raise ValidationError(
            "Frete/desconto com itens de valor zero exige rateio manual; não invente uma divisão."
        )
    cents = int(amount * 100)
    raw = [Decimal(cents) * weight / total for weight in weights]
    portions = [int(value) for value in raw]
    order = sorted(
        range(len(raw)), key=lambda index: (-(raw[index] - portions[index]), index)
    )
    for index in order[: cents - sum(portions)]:
        portions[index] += 1
    return [Decimal(value) / 100 for value in portions]


@transaction.atomic
def add_item(
    *, owner, purchase_id, material_id, quantity, unit_price, unit=None, lot=""
):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    purchase = get_object_or_404(
        Purchase.objects.select_for_update(), pk=purchase_id, owner=owner
    )
    if purchase.status != "draft":
        raise ValidationError("Somente compras em rascunho podem receber itens.")
    material = get_object_or_404(
        Material, pk=material_id, owner=owner, is_archived=False
    )
    base, snapshot = to_base(material, quantity, unit)
    if unit_price < 0:
        raise ValidationError("Preço não pode ser negativo.")
    item = PurchaseItem(
        purchase=purchase,
        material=material,
        quantity=quantity,
        unit=unit or material.unit,
        base_quantity=base,
        conversion_snapshot=snapshot,
        unit_price=unit_price,
        lot=lot,
    )
    item.full_clean(exclude=["allocated_cost"])
    item.save()
    return item


@transaction.atomic
def confirm_purchase(*, owner, purchase_id, manual_allocations=None):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    purchase = get_object_or_404(
        Purchase.objects.select_for_update(), pk=purchase_id, owner=owner
    )
    if purchase.status in {"confirmed", "partial", "received"}:
        if manual_allocations is not None:
            supplied = {str(pk): value for pk, value in manual_allocations.items()}
            stored = {
                str(item.pk): item.allocated_cost for item in purchase.items.all()
            }
            if supplied != stored or purchase.allocation_mode != "manual":
                raise ValidationError(
                    "O rateio já foi confirmado e não pode ser substituído."
                )
        return purchase
    if purchase.status != "draft":
        raise ValidationError("Esta compra não pode ser confirmada.")
    items = list(purchase.items.select_related("material").order_by("id"))
    if not items:
        raise ValidationError("Adicione pelo menos um item antes de confirmar.")
    if any(item.material.owner_id != owner.pk for item in items):
        raise ValidationError("Material não pertence a esta conta.")
    weights = [item.net_total for item in items]
    if purchase.discount > sum(weights, Decimal(0)):
        raise ValidationError("Desconto não pode superar o valor dos itens.")
    if manual_allocations is not None:
        costs = {str(pk): value for pk, value in manual_allocations.items()}
        if set(costs) != {str(item.pk) for item in items}:
            raise ValidationError(
                "Informe o custo final de todos os itens desta compra, sem itens de outra compra."
            )
        if any(
            not isinstance(value, Decimal)
            or not value.is_finite()
            or value < 0
            or value > Decimal("9999999999.99")
            or value != value.quantize(CENT)
            for value in costs.values()
        ):
            raise ValidationError(
                "Custos finais devem ser valores não negativos, com até duas casas decimais."
            )
        if sum(costs.values(), Decimal(0)) != purchase.total:
            raise ValidationError(
                "A soma dos custos finais precisa ser exatamente o total da compra, incluindo frete e desconto."
            )
        purchase.allocation_mode = "manual"
    else:
        freight = distribute(purchase.freight, weights)
        discount = distribute(purchase.discount, weights)
        costs = {
            str(item.pk): item.net_total + f - d
            for item, f, d in zip(items, freight, discount)
        }
        purchase.allocation_mode = "auto"
    for item in items:
        item.allocated_cost = costs[str(item.pk)]
        item.full_clean()
        item.save(update_fields=["allocated_cost"])
    purchase.status = "confirmed"
    purchase.save(update_fields=["status", "allocation_mode"])
    return purchase


@transaction.atomic
def receive_purchase(*, owner, purchase_id, quantities, key):
    op, repeated = begin_operation(
        owner,
        key,
        "purchase_receipt",
        {
            "purchase": purchase_id,
            "quantities": {str(k): str(v) for k, v in quantities.items()},
        },
    )
    if repeated:
        return op.result
    purchase = get_object_or_404(
        Purchase.objects.select_for_update(), pk=purchase_id, owner=owner
    )
    if purchase.status not in {"confirmed", "partial"}:
        raise ValidationError(
            "Confirme a compra antes de receber; compras canceladas/concluídas não recebem novas entradas."
        )
    if not quantities:
        raise ValidationError("Informe pelo menos um item recebido.")
    receipt = Receipt.objects.create(purchase=purchase, key=op.pk)
    for item_id, quantity in sorted(quantities.items(), key=lambda pair: str(pair[0])):
        valid_quantity(quantity)
        item = get_object_or_404(
            PurchaseItem.objects.select_for_update(), pk=item_id, purchase=purchase
        )
        if item.material.owner_id != owner.pk:
            raise ValidationError("Vínculo de material inválido.")
        if quantity > item.remaining:
            raise ValidationError("O recebido ultrapassaria a quantidade contratada.")
        cost = (item.allocated_cost / item.base_quantity).quantize(
            Decimal(".000001"), rounding=ROUND_HALF_UP
        )
        result = receive_stock(
            owner=owner,
            material_id=item.material_id,
            quantity=quantity,
            unit_cost=cost,
            key=uuid.uuid5(key, str(item.pk)),
            lot=item.lot,
            reason="Recebimento de compra",
            source_conversion=item.conversion_snapshot,
        )
        ReceiptLine.objects.create(
            receipt=receipt, item=item, layer_id=result["layer"], quantity=quantity
        )
        item.received += quantity
        item.save(update_fields=["received"])
    purchase.status = (
        "received"
        if all(item.received == item.base_quantity for item in purchase.items.all())
        else "partial"
    )
    purchase.save(update_fields=["status"])
    return finish(op, {"receipt": str(receipt.pk), "status": purchase.status})


@transaction.atomic
def cancel_purchase(*, owner, purchase_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    purchase = get_object_or_404(
        Purchase.objects.select_for_update(), pk=purchase_id, owner=owner
    )
    if purchase.status == "received":
        raise ValidationError(
            "Uma compra recebida exige devolução/retificação, não cancelamento da entrada."
        )
    purchase.status = "cancelled"
    purchase.save(update_fields=["status"])
    return purchase


@transaction.atomic
def repeat_purchase(*, owner, purchase_id, date):
    original = get_object_or_404(Purchase, pk=purchase_id, owner=owner)
    new = Purchase.objects.create(
        owner=owner,
        supplier=original.supplier,
        date=date,
        freight=original.freight,
        discount=original.discount,
        notes=original.notes,
    )
    for item in original.items.all():
        add_item(
            owner=owner,
            purchase_id=new.pk,
            material_id=item.material_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            unit=item.unit,
            lot="",
        )
    return new


@transaction.atomic
def edit_item(*, owner, item_id, material_id, quantity, unit_price, unit=None, lot=""):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    old = get_object_or_404(
        PurchaseItem.objects.select_related("purchase"),
        pk=item_id,
        purchase__owner=owner,
    )
    if old.purchase.status != "draft":
        raise ValidationError("Somente itens de rascunho podem ser editados.")
    replacement = add_item(
        owner=owner,
        purchase_id=old.purchase_id,
        material_id=material_id,
        quantity=quantity,
        unit_price=unit_price,
        unit=unit,
        lot=lot,
    )
    old.delete()
    return replacement


@transaction.atomic
def remove_item(*, owner, item_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    item = get_object_or_404(PurchaseItem, pk=item_id, purchase__owner=owner)
    if item.purchase.status != "draft":
        raise ValidationError("Somente itens de rascunho podem ser removidos.")
    item.delete()
