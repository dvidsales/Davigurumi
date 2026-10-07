import smtplib
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import Notification, NotificationPreference, OutboxEvent, AuditEvent


@transaction.atomic
def emit(*, owner, kind, object_id, message):
    notification, created = Notification.objects.get_or_create(
        owner=owner, key=f"{kind}:{object_id}", defaults={"message": message[:240]}
    )
    if created:
        AuditEvent.objects.create(owner=owner, action=kind, object_id=object_id)
        if NotificationPreference.objects.filter(
            owner=owner, email_enabled=True
        ).exists():
            OutboxEvent.objects.create(notification=notification)
    return notification


def deliver_outbox(limit=50):
    sent = failed = 0
    for _ in range(limit):
        with transaction.atomic():
            from django.db import connection

            rows = OutboxEvent.objects.filter(
                status="pending", next_attempt__lte=timezone.now()
            ).order_by("next_attempt", "id")
            rows = rows.select_for_update(
                skip_locked=connection.features.has_select_for_update_skip_locked
            )
            row = rows.first()
            if row is None:
                break
            row.attempts += 1
            try:
                send_mail(
                    "Atualização no Davigurumi",
                    row.notification.message,
                    settings.DEFAULT_FROM_EMAIL,
                    [row.notification.owner.email],
                    fail_silently=False,
                )
            except (smtplib.SMTPException, OSError) as exc:
                row.last_error = type(exc).__name__
                row.next_attempt = timezone.now() + timedelta(
                    seconds=min(3600, 30 * 2 ** min(row.attempts, 7))
                )
                failed += 1
            else:
                row.status = "sent"
                row.sent_at = timezone.now()
                row.last_error = ""
                sent += 1
            row.save()
    return {"sent": sent, "failed": failed}


@transaction.atomic
def generate_alerts(owner, today=None):
    from django.contrib.auth import get_user_model
    from materials.models import Material
    from production.models import Order
    from finance.services import installment_balances
    from .reporting import replenishment, below_minimum

    today = today or timezone.localdate()
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    before = Notification.objects.filter(owner=owner).count()
    for row in below_minimum(owner):
        emit(
            owner=owner,
            kind="minimum_stock:" + today.isoformat(),
            object_id=row["material"].pk,
            message=f"Estoque abaixo do mínimo: {row['material'].name}, disponível {row['available']} {row['material'].unit}; mínimo {row['material'].minimum_stock}.",
        )
    for row in replenishment(owner):
        emit(
            owner=owner,
            kind="shortage:" + today.isoformat(),
            object_id=row["material"].pk,
            message=f"Reposição: faltam {row['quantity']} {row['material'].unit} de {row['material'].name} para pedidos em aberto.",
        )
    for order in Order.objects.filter(owner=owner).exclude(status="cancelled"):
        if (
            order.status in ("waiting", "in_progress", "paused")
            and order.production_due
            and order.production_due <= today + timedelta(days=2)
        ):
            emit(
                owner=owner,
                kind="production_due:" + today.isoformat(),
                object_id=order.pk,
                message=f"Pedido {order.approved_version.quote.number}: prazo de produção em {order.production_due:%d/%m/%Y}.",
            )
        for row in installment_balances(order):
            installment = row["receivable"]
            if row["balance"] > 0 and installment.due_date <= today + timedelta(days=3):
                emit(
                    owner=owner,
                    kind="payment_due:" + today.isoformat(),
                    object_id=installment.pk,
                    message=f"Parcela {installment.label or 'prevista'} do pedido {order.approved_version.quote.number}: saldo R$ {row['balance']:.2f}, vencimento {installment.due_date:%d/%m/%Y}.",
                )
    return Notification.objects.filter(owner=owner).count() - before
