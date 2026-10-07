from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal(".01")


def cost_summary(order):
    estimate = materials = reserved = labor = Decimal(0)
    estimate_complete = materials_complete = reserved_complete = True
    for item in order.items.prefetch_related(
        "consumptions__movement", "sessions__corrections"
    ):
        estimate += Decimal(item.snapshot.get("cost", "0"))
        estimate_complete &= bool(item.snapshot.get("complete", False))
        for consumption in item.consumptions.all():
            movement = consumption.movement
            if movement.unit_cost is None:
                materials_complete = False
            else:
                materials += -movement.quantity * movement.unit_cost
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
    return {
        "estimate": estimate.quantize(CENT, rounding=ROUND_HALF_UP),
        "estimate_complete": estimate_complete,
        "materials": materials.quantize(CENT, rounding=ROUND_HALF_UP),
        "materials_complete": materials_complete,
        "reserved": reserved.quantize(CENT, rounding=ROUND_HALF_UP),
        "reserved_complete": reserved_complete,
        "labor": labor.quantize(CENT, rounding=ROUND_HALF_UP),
    }
