import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from materials.models import StockReservation, StockMovement
from materials.stock import (
    begin_operation,
    finish,
    reserve_stock,
    consume_reserved,
    consume_available,
    release_reservation,
)
from operations.models import AuditEvent
from operations.services import emit
from sales.models import QuoteVersion
from .models import (
    Order,
    OrderItem,
    Consumption,
    ProductionSession,
    SessionCorrection,
    DeliveryEvent,
)


@transaction.atomic
def create_order(*, owner, version_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(
        QuoteVersion.objects.select_related("quote"), pk=version_id, quote__owner=owner
    )
    existing = Order.objects.filter(approved_version=version).first()
    if existing:
        return existing
    if (
        version.status != "approved"
        or version.approved_hash != version.content_hash
        or version.approval_origin != "link"
    ):
        raise ValidationError(
            "O pedido exige novo aceite da versão publicada exata; aceite importado é apenas histórico."
        )
    if Order.objects.filter(approved_version__quote=version.quote).exists():
        raise ValidationError(
            "Esta aprovação pertence a um orçamento já convertido. Aplique o aditivo ao pedido existente."
        )
    order = Order.objects.create(
        owner=owner, approved_version=version, current_version=version
    )
    for source in version.items.all():
        OrderItem.objects.create(
            order=order,
            source_item=source,
            line_key=source.line_key,
            description=source.description,
            quantity=source.quantity,
            snapshot=source.snapshot,
        )
    from finance.models import PaymentAllocation

    PaymentAllocation.objects.filter(version=version, order__isnull=True).update(
        order=order
    )
    emit(
        owner=owner,
        kind="order_created",
        object_id=order.pk,
        message=f"Pedido criado a partir do orçamento {version.quote.number}.",
    )
    return order


@transaction.atomic
def reserve_order(*, owner, order_id, key):
    from materials.stock import net_consumed

    op, repeated = begin_operation(owner, key, "order_reserve", {"order": order_id})
    if repeated:
        return op.result
    order = get_object_or_404(
        Order.objects.select_for_update(), pk=order_id, owner=owner
    )
    if order.status in {"completed", "cancelled"}:
        raise ValidationError("Pedido encerrado não pode receber reservas.")
    result = []
    for item in order.items.filter(retired=False):
        requirements = {}
        for line in item.snapshot["materials"]:
            material_id = line["material"]
            requirements[material_id] = requirements.get(
                material_id, Decimal(0)
            ) + Decimal(line["quantity"])
        for material_id, needed in sorted(requirements.items()):
            consumed = sum(
                (
                    net_consumed(row.movement)
                    for row in item.consumptions.select_related("movement")
                    if str(row.movement.material_id) == material_id
                ),
                Decimal(0),
            )
            reserved = sum(
                (
                    row.remaining
                    for row in StockReservation.objects.filter(
                        reference=item.pk, layer__material_id=material_id
                    )
                ),
                Decimal(0),
            )
            missing = max(Decimal(0), needed - consumed - reserved)
            if missing:
                result.append(
                    reserve_stock(
                        owner=owner,
                        material_id=material_id,
                        quantity=missing,
                        key=uuid.uuid5(key, str(item.pk) + material_id),
                        reference=item.pk,
                        label=item.description,
                    )
                )
    return finish(op, {"allocations": result})


@transaction.atomic
def consume_item(*, owner, item_id, material_id, quantity, key, reservation_id=None):
    op, repeated = begin_operation(
        owner,
        key,
        "order_consume",
        {
            "item": item_id,
            "material": material_id,
            "quantity": quantity,
            "reservation": reservation_id,
        },
    )
    if repeated:
        return op.result
    item = get_object_or_404(
        OrderItem.objects.select_for_update(),
        pk=item_id,
        order__owner=owner,
        retired=False,
    )
    if item.order.status in {"completed", "cancelled"}:
        raise ValidationError("Pedido encerrado não pode consumir novos materiais.")
    if reservation_id:
        reservation = get_object_or_404(
            StockReservation,
            pk=reservation_id,
            reference=item.pk,
            layer__material_id=material_id,
            layer__material__owner=owner,
        )
        result = consume_reserved(
            owner=owner,
            reservation_id=reservation.pk,
            quantity=quantity,
            key=uuid.uuid5(key, "reserved"),
        )
        movements = [result["movement"]]
    else:
        result = consume_available(
            owner=owner,
            material_id=material_id,
            quantity=quantity,
            key=uuid.uuid5(key, "available"),
            reason="Consumo de pedido",
        )
        movements = result["movements"]
    for movement_id in movements:
        Consumption.objects.create(item=item, movement_id=movement_id)
    return finish(op, {"movements": movements, "cost": result["cost"]})


@transaction.atomic
def start_session(*, owner, item_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    item = get_object_or_404(OrderItem, pk=item_id, order__owner=owner, retired=False)
    if item.order.status in {"completed", "cancelled"}:
        raise ValidationError("O pedido está encerrado.")
    current = ProductionSession.objects.filter(
        owner=owner, ended_at__isnull=True
    ).first()
    if current:
        if current.item_id == item.pk:
            return current
        raise ValidationError(
            "Você já tem uma sessão ativa. Pause a sessão anterior antes de iniciar outra."
        )
    row = ProductionSession.objects.create(
        owner=owner,
        item=item,
        started_at=timezone.now(),
        hourly_rate=Decimal(item.snapshot["hourly_rate"]),
    )
    Order.objects.filter(pk=item.order_id).update(status="in_progress")
    return row


@transaction.atomic
def stop_session(*, owner, session_id):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    row = get_object_or_404(
        ProductionSession.objects.select_for_update(), pk=session_id, owner=owner
    )
    if row.ended_at:
        return row
    row.ended_at = timezone.now()
    row.seconds = max(0, int((row.ended_at - row.started_at).total_seconds()))
    row.save(update_fields=["ended_at", "seconds"])
    Order.objects.filter(pk=row.item.order_id, status="in_progress").update(
        status="paused"
    )
    return row


@transaction.atomic
def manual_time(*, owner, item_id, seconds, ended_at=None):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    item = get_object_or_404(OrderItem, pk=item_id, order__owner=owner, retired=False)
    if item.order.status == "cancelled":
        raise ValidationError("Pedido cancelado não recebe nova sessão de tempo.")
    if not isinstance(seconds, int) or seconds < 0 or seconds > 86400 * 30:
        raise ValidationError("Duração inválida; use até 30 dias em segundos.")
    end = ended_at or timezone.now()
    start = end - timedelta(seconds=seconds)
    overlapping = (
        ProductionSession.objects.filter(owner=owner, started_at__lt=end)
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gt=start))
        .exists()
    )
    if overlapping:
        raise ValidationError(
            "O intervalo se sobrepõe a outra sessão. Pause/revise a sessão existente."
        )
    return ProductionSession.objects.create(
        owner=owner,
        item=item,
        started_at=start,
        ended_at=end,
        seconds=seconds,
        origin="manual",
        hourly_rate=Decimal(item.snapshot["hourly_rate"]),
    )


@transaction.atomic
def correct_time(*, owner, session_id, seconds, reason):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    session = get_object_or_404(
        ProductionSession, pk=session_id, owner=owner, ended_at__isnull=False
    )
    if (
        not isinstance(seconds, int)
        or seconds < 0
        or seconds > 86400 * 30
        or not reason.strip()
    ):
        raise ValidationError("Informe duração válida e motivo da correção.")
    correction = SessionCorrection.objects.create(
        session=session, seconds=seconds, reason=reason[:200]
    )
    AuditEvent.objects.create(
        owner=owner, action="time_corrected", object_id=session.pk, reason=reason[:200]
    )
    return correction


@transaction.atomic
def record_produced(*, owner, item_id, quantity):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    item = get_object_or_404(
        OrderItem.objects.select_for_update(),
        pk=item_id,
        order__owner=owner,
        retired=False,
    )
    if item.order.status in {"completed", "cancelled"}:
        raise ValidationError("Pedido encerrado não recebe produção.")
    if (
        not isinstance(quantity, int)
        or quantity < 0
        or quantity > item.quantity
        or quantity < item.delivered
    ):
        raise ValidationError(
            "Quantidade produzida deve ficar entre o entregue e o contratado."
        )
    item.produced = quantity
    item.save(update_fields=["produced"])
    return item


@transaction.atomic
def deliver_item(*, owner, item_id, quantity, key, notes=""):
    op, repeated = begin_operation(
        owner, key, "delivery", {"item": item_id, "quantity": quantity, "notes": notes}
    )
    if repeated:
        return op.result
    item = get_object_or_404(
        OrderItem.objects.select_for_update(),
        pk=item_id,
        order__owner=owner,
        retired=False,
    )
    if (
        item.order.status == "cancelled"
        or not isinstance(quantity, int)
        or quantity <= 0
        or item.delivered + quantity > item.produced
    ):
        raise ValidationError(
            "Entrega deve corresponder a uma quantidade produzida e ainda não entregue."
        )
    item.delivered += quantity
    item.save(update_fields=["delivered"])
    event = DeliveryEvent.objects.create(
        item=item, quantity=quantity, notes=notes[:200]
    )
    order = item.order
    if all(row.delivered == row.quantity for row in order.items.filter(retired=False)):
        order.delivery_status = "delivered"
        order.save(update_fields=["delivery_status"])
    return finish(op, {"event": event.pk, "delivered": item.delivered})


@transaction.atomic
def close_order(*, owner, order_id, status, reason=""):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    order = get_object_or_404(
        Order.objects.select_for_update(), pk=order_id, owner=owner
    )
    if status not in {"completed", "cancelled", "waiting"}:
        raise ValidationError("Estado inválido.")
    if order.status == status:
        return order
    if status == "waiting":
        if order.status not in {"completed", "cancelled"} or not reason.strip():
            raise ValidationError("Reabertura exige pedido encerrado e um motivo.")
    else:
        if ProductionSession.objects.filter(
            item__order=order, ended_at__isnull=True
        ).exists():
            raise ValidationError("Pause a sessão ativa antes de encerrar o pedido.")
        if status == "completed" and any(
            item.produced != item.quantity for item in order.items.filter(retired=False)
        ):
            raise ValidationError(
                "Registre as quantidades produzidas antes de concluir."
            )
        for reservation in StockReservation.objects.filter(
            reference__in=order.items.values_list("pk", flat=True), remaining__gt=0
        ):
            release_reservation(
                owner=owner, reservation_id=reservation.pk, key=uuid.uuid4()
            )
    order.status = status
    order.save(update_fields=["status"])
    AuditEvent.objects.create(
        owner=owner, action="order_" + status, object_id=order.pk, reason=reason[:200]
    )
    emit(
        owner=owner,
        kind="order_" + status,
        object_id=order.pk,
        message=f"Pedido: {order.get_status_display().lower()}.",
    )
    return order


@transaction.atomic
def apply_amendment(*, owner, order_id, version_id, reconciliation_reason=""):
    from materials.stock import net_consumed

    if len(reconciliation_reason) > 200:
        raise ValidationError("O motivo de conciliação deve ter até 200 caracteres.")
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    order = get_object_or_404(
        Order.objects.select_for_update(), pk=order_id, owner=owner
    )
    version = get_object_or_404(
        QuoteVersion, pk=version_id, quote__owner=owner, status="approved"
    )
    if order.current_version_id == version.pk:
        return order
    if (
        version.approval_origin != "link"
        or not version.published_at
        or not version.content_hash
        or version.approved_hash != version.content_hash
    ):
        raise ValidationError(
            "O aditivo exige novo aceite da versão publicada exata; aceite importado é apenas histórico."
        )
    if (
        version.amends_version_id != order.current_version_id
        or version.quote_id != order.approved_version.quote_id
    ):
        raise ValidationError(
            "O aditivo precisa aprovar a condição comercial vigente deste pedido."
        )
    if order.status in {"completed", "cancelled"}:
        raise ValidationError("Reabra o pedido com motivo antes de aplicar um aditivo.")
    new_items = {item.line_key: item for item in version.items.all()}
    for item in order.items.all():
        new = new_items.pop(item.line_key, None)
        changed_materials = new is None or new.snapshot.get(
            "materials", []
        ) != item.snapshot.get("materials", [])
        if new is None and item.retired:
            continue
        if new is None and (item.produced or item.delivered):
            raise ValidationError(
                "Um item produzido/entregue não pode ser removido por este fluxo."
            )
        if new is not None and new.quantity < max(item.produced, item.delivered):
            raise ValidationError(
                "Aditivo não pode reduzir quantidade já produzida/entregue."
            )
        if new is not None and (item.produced or item.delivered):

            def recipe(snapshot, quantity):
                result = {}
                for line in snapshot.get("materials", []):
                    identity = (line["material"], line["unit"])
                    result[identity] = (
                        result.get(identity, Decimal(0))
                        + Decimal(line["quantity"]) / quantity
                    )
                return result

            if recipe(new.snapshot, new.quantity) != recipe(
                item.snapshot, item.quantity
            ):
                raise ValidationError(
                    "A composição de um item produzido/entregue não pode ser substituída por este fluxo."
                )
        if changed_materials:
            if item.sessions.filter(ended_at__isnull=True).exists():
                raise ValidationError(
                    "Pause o cronômetro do item antes de conciliar materiais."
                )
            consumed = sum(
                (
                    net_consumed(entry.movement)
                    for entry in item.consumptions.select_related("movement")
                ),
                Decimal(0),
            )
            if consumed > 0 and not reconciliation_reason.strip():
                raise ValidationError(
                    "Informe o motivo da conciliação: materiais já usados permanecem como consumo/custo histórico. Recupere somente sobras físicas pelo fluxo próprio."
                )
            for reservation in StockReservation.objects.filter(
                reference=item.pk, remaining__gt=0, layer__material__owner=owner
            ):
                release_reservation(
                    owner=owner,
                    reservation_id=reservation.pk,
                    key=uuid.uuid5(
                        version.pk, "amendment_release_" + str(reservation.pk)
                    ),
                )
        if new is None:
            item.retired = True
            item.save(update_fields=["retired"])
        else:
            item.retired = False
            item.quantity = new.quantity
            item.description = new.description
            item.snapshot = new.snapshot
            item.save(update_fields=["retired", "quantity", "description", "snapshot"])
    for new in new_items.values():
        OrderItem.objects.create(
            order=order,
            source_item=new,
            line_key=new.line_key,
            description=new.description,
            quantity=new.quantity,
            snapshot=new.snapshot,
        )
    order.current_version = version
    if (
        order.delivery_status == "delivered"
        and order.items.filter(retired=False).exclude(delivered=F("quantity")).exists()
    ):
        order.delivery_status = "not_sent"
    order.save(update_fields=["current_version", "delivery_status"])
    from finance.models import PaymentAllocation

    PaymentAllocation.objects.filter(version=version, order__isnull=True).update(
        order=order
    )
    AuditEvent.objects.create(
        owner=owner,
        action="amendment_applied",
        object_id=order.pk,
        reason=(f"Versão {version.number}: " + reconciliation_reason)[:200],
    )
    return order


@transaction.atomic
def record_expense(*, owner, order_id, amount, date, description, key, reverses=None):
    from .models import ActualExpense
    from datetime import date as Date

    if (
        not isinstance(amount, Decimal)
        or not amount.is_finite()
        or amount <= 0
        or amount > Decimal("9999999999.99")
        or amount != amount.quantize(Decimal(".01"))
    ):
        raise ValidationError(
            "Informe uma despesa positiva com até duas casas decimais."
        )
    if not isinstance(date, Date) or not description.strip() or len(description) > 200:
        raise ValidationError("Informe data e descrição de até 200 caracteres.")
    op, repeated = begin_operation(
        owner,
        key,
        "order_expense",
        {
            "order": order_id,
            "amount": amount,
            "date": date,
            "description": description,
            "reverses": reverses,
        },
    )
    if repeated:
        return op.result
    order = get_object_or_404(
        Order.objects.select_for_update(), pk=order_id, owner=owner
    )
    original = None
    if reverses:
        original = get_object_or_404(
            ActualExpense.objects.select_for_update(),
            pk=reverses,
            order=order,
            reverses__isnull=True,
        )
        if (
            ActualExpense.objects.filter(reverses=original).exists()
            or amount != original.amount
        ):
            raise ValidationError(
                "A reversão precisa ter o valor original e só pode ser registrada uma vez."
            )
    expense = ActualExpense.objects.create(
        order=order,
        key=op.pk,
        amount=amount,
        date=date,
        description=description,
        reverses=original,
    )
    AuditEvent.objects.create(
        owner=owner,
        action="expense_reversed" if original else "expense_recorded",
        object_id=expense.pk,
        reason=description,
    )
    return finish(op, {"expense": str(expense.pk)})
