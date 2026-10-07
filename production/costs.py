from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal(".01")


def cost_summary(order):
    from materials.stock import net_consumed

    estimate = materials = reserved = labor = Decimal(0)
    estimate_complete = materials_complete = reserved_complete = True
    for item in order.items.prefetch_related(
        "consumptions__movement", "sessions__corrections"
    ):
        if not item.retired:
            estimate += Decimal(item.snapshot.get("cost", "0"))
            estimate_complete &= bool(item.snapshot.get("complete", False))
        for consumption in item.consumptions.all():
            movement = consumption.movement
            quantity = net_consumed(movement)
            if quantity <= 0:
                continue
            if movement.unit_cost is None:
                materials_complete = False
            else:
                materials += quantity * movement.unit_cost
        for session in item.sessions.all():
            if session.ended_at:
                labor += Decimal(session.effective_seconds) / 3600 * session.hourly_rate
        from materials.models import StockReservation

        for reservation in StockReservation.objects.filter(
            reference=item.pk, layer__material__owner=order.owner
        ).select_related("layer"):
            if reservation.remaining <= 0:
                continue
            if reservation.layer.unit_cost is None:
                reserved_complete = False
            else:
                reserved += reservation.remaining * reservation.layer.unit_cost
    expenses = sum(
        (
            (-entry.amount if entry.reverses_id else entry.amount)
            for entry in order.expenses.all()
        ),
        Decimal(0),
    )
    active_time = order.items.filter(
        sessions__ended_at__isnull=True, sessions__id__isnull=False
    ).exists()
    known_total = materials + labor + expenses
    return {
        "expenses": expenses,
        "actual_known_total": known_total.quantize(CENT, rounding=ROUND_HALF_UP),
        "recorded_result": (order.total - known_total).quantize(
            CENT, rounding=ROUND_HALF_UP
        ),
        "actual_complete": materials_complete and not active_time,
        "estimate": estimate.quantize(CENT, rounding=ROUND_HALF_UP),
        "estimate_complete": estimate_complete,
        "materials": materials.quantize(CENT, rounding=ROUND_HALF_UP),
        "materials_complete": materials_complete,
        "reserved": reserved.quantize(CENT, rounding=ROUND_HALF_UP),
        "reserved_complete": reserved_complete,
        "labor": labor.quantize(CENT, rounding=ROUND_HALF_UP),
    }
