from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from finance.models import Payment, PaymentAllocation, Refund
from materials.models import Material
from materials.stock import receive_stock
from projects.services import create_project, add_material
from sales.services import create_quote, add_quote_item, publish, decide
from production.services import create_order, reserve_order, consume_item
from .reporting import cash_period, replenishment
import uuid

D = Decimal


class ReportingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="report", email="report@example.test"
        )

    def test_cash_period_uses_receipt_and_refund_dates_independently(self):
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        previous = Payment.objects.create(
            owner=self.owner, amount=D("50"), date=date(2026, 9, 30), method="pix"
        )
        current = Payment.objects.create(
            owner=self.owner, amount=D("30"), date=date(2026, 10, 1), method="pix"
        )
        allocation = PaymentAllocation.objects.create(
            payment=previous, version=version, amount=previous.amount
        )
        Refund.objects.create(
            allocation=allocation,
            amount=D("10"),
            date=date(2026, 10, 2),
            reason="Reversão",
        )
        self.assertEqual(
            cash_period(self.owner, date(2026, 10, 1), date(2026, 10, 31)),
            {"receipts": D("30"), "refunds": D("10"), "net": D("20")},
        )

    def test_replenishment_counts_duplicate_material_lines_once_per_requirement(self):
        material = Material.objects.create(
            owner=self.owner, name="Fio", kind="yarn", unit="g"
        )
        receive_stock(
            owner=self.owner,
            material_id=material.pk,
            quantity=D("100"),
            unit_cost=D(".1"),
            key=uuid.uuid4(),
        )
        project = create_project(owner=self.owner, name="Peça")
        add_material(
            owner=self.owner,
            project_id=project.pk,
            material_id=material.pk,
            quantity=D("60"),
        )
        add_material(
            owner=self.owner,
            project_id=project.pk,
            material_id=material.pk,
            quantity=D("60"),
        )
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        add_quote_item(
            owner=self.owner, version_id=version.pk, project_id=project.pk, quantity=1
        )
        _, raw = publish(owner=self.owner, version_id=version.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        order = create_order(owner=self.owner, version_id=version.pk)
        consume_item(
            owner=self.owner,
            item_id=order.items.get().pk,
            material_id=material.pk,
            quantity=D("10"),
            key=uuid.uuid4(),
        )
        self.assertEqual(replenishment(self.owner)[0]["quantity"], D("20"))

    def test_due_alerts_are_deduplicated_and_do_not_create_cash(self):
        from django.utils import timezone
        from finance.services import add_receivable
        from .services import generate_alerts
        from .models import Notification

        project = create_project(
            owner=self.owner, name="Peça", estimated_seconds=3600, hourly_rate=D("30")
        )
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        add_quote_item(
            owner=self.owner, version_id=version.pk, project_id=project.pk, quantity=1
        )
        _, raw = publish(owner=self.owner, version_id=version.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        order = create_order(owner=self.owner, version_id=version.pk)
        order.production_due = timezone.localdate()
        order.save(update_fields=["production_due"])
        add_receivable(
            owner=self.owner,
            order_id=order.pk,
            amount=D("10"),
            due_date=timezone.localdate(),
            label="Sinal",
        )
        self.assertEqual(generate_alerts(self.owner), 2)
        self.assertEqual(generate_alerts(self.owner), 0)
        self.assertFalse(Payment.objects.filter(owner=self.owner).exists())
