import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from projects.services import create_project
from sales.services import create_quote, add_quote_item, publish, decide
from production.services import create_order, close_order
from .models import Payment, Refund, PaymentAllocation
from .services import (
    record_payment,
    refund_payment,
    add_receivable,
    installment_balances,
)

D = Decimal


class PaymentTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="cash", email="cash@example.test"
        )
        project = create_project(
            owner=self.owner,
            name="Peça",
            estimated_seconds=3600,
            hourly_rate=D("100"),
            percentage=D(0),
        )
        self.quote = create_quote(owner=self.owner)
        self.version = self.quote.versions.get()
        add_quote_item(
            owner=self.owner,
            version_id=self.version.pk,
            project_id=project.pk,
            quantity=1,
        )
        _, raw = publish(owner=self.owner, version_id=self.version.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        self.today = timezone.localdate()

    def payment(self, amount, key=None):
        return record_payment(
            owner=self.owner,
            version_id=self.version.pk,
            amount=D(amount),
            date=self.today,
            method="pix",
            key=key or uuid.uuid4(),
        )

    def test_deposit_conversion_preserves_single_payment_allocation(self):
        result = self.payment("50")
        order = create_order(owner=self.owner, version_id=self.version.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentAllocation.objects.get().order, order)
        self.assertEqual(order.net_received, D("50"))

    def test_prd_partial_receipts_and_refund(self):
        order = create_order(owner=self.owner, version_id=self.version.pk)
        first = self.payment("50")
        self.payment("30")
        refund_payment(
            owner=self.owner,
            allocation_id=first["allocation"],
            amount=D("10"),
            date=self.today,
            reason="Correção",
            key=uuid.uuid4(),
        )
        self.assertEqual(order.net_received, D("70"))
        self.assertEqual(order.balance, D("30"))
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(Refund.objects.count(), 1)

    def test_payment_retry_is_idempotent_and_excess_requires_confirmation(self):
        key = uuid.uuid4()
        first = self.payment("80", key)
        self.assertEqual(self.payment("80", key), first)
        with self.assertRaises(ValidationError):
            self.payment("30")
        record_payment(
            owner=self.owner,
            version_id=self.version.pk,
            amount=D("30"),
            date=self.today,
            method="cash",
            key=uuid.uuid4(),
            allow_credit=True,
        )
        order = create_order(owner=self.owner, version_id=self.version.pk)
        self.assertEqual(order.credit, D("10"))
        self.assertEqual(order.balance, 0)

    def test_over_refund_is_rejected_and_cancel_preserves_cash(self):
        first = self.payment("50")
        order = create_order(owner=self.owner, version_id=self.version.pk)
        with self.assertRaises(ValidationError):
            refund_payment(
                owner=self.owner,
                allocation_id=first["allocation"],
                amount=D("51"),
                date=self.today,
                reason="Erro",
                key=uuid.uuid4(),
            )
        close_order(owner=self.owner, order_id=order.pk, status="cancelled")
        order.refresh_from_db()
        self.assertEqual(order.net_received, D("50"))
        self.assertEqual(order.financial_status, "Pendência de reembolso")

    def test_installments_do_not_increase_cash_and_oldest_due_is_applied_once(self):
        order = create_order(owner=self.owner, version_id=self.version.pk)
        add_receivable(
            owner=self.owner,
            order_id=order.pk,
            amount=D("50"),
            due_date=self.today,
            label="Sinal",
        )
        add_receivable(
            owner=self.owner,
            order_id=order.pk,
            amount=D("50"),
            due_date=self.today,
            label="Restante",
        )
        self.assertEqual(order.net_received, 0)
        self.payment("70")
        balances = installment_balances(order)
        self.assertEqual(sum(row["balance"] for row in balances), D("30"))
