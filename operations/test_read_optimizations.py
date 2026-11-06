import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from finance.models import PaymentAllocation
from finance.services import record_payment, refund_payment
from materials.models import Material
from materials.selectors import stock_levels
from materials.stock import (
    reserve_stock,
    consume_reserved,
    receive_stock,
    compensate_movement,
)
from production.models import Order
from production.selectors import outstanding_balances
from production.test_read_queries import ReadFixture
from .reporting import overview, below_minimum


class ReadOptimizationTests(ReadFixture, TestCase):
    def test_balance_projection_matches_reference_with_multiple_refunds_and_cancelled(
        self,
    ):
        today = timezone.localdate()
        for _ in range(2):
            record_payment(
                owner=self.owner,
                version_id=self.order.current_version_id,
                amount=Decimal(5),
                date=today,
                method="pix",
                key=uuid.uuid4(),
            )
        for allocation in PaymentAllocation.objects.filter(order=self.order):
            for _ in range(2):
                refund_payment(
                    owner=self.owner,
                    allocation_id=allocation.pk,
                    amount=Decimal(1),
                    date=today,
                    reason="Synthetic refund",
                    key=uuid.uuid4(),
                )
        cancelled = self.make_order(1)
        Order.objects.filter(pk=cancelled.pk).update(status="cancelled")
        for row in outstanding_balances(self.owner):
            self.assertEqual(row.ledger_balance, row.balance)
        expected = sum(
            (
                order.balance
                for order in Order.objects.filter(owner=self.owner).exclude(
                    status="cancelled"
                )
            ),
            Decimal(0),
        )
        self.assertEqual(overview(self.owner)["open_balance"], expected)
        other = get_user_model().objects.create_user(
            username="other-projection", email="other-projection@example.test"
        )
        self.assertFalse(outstanding_balances(other).exists())

    def test_stock_projection_matches_ledger_after_reservation_consumption_and_compensation(
        self,
    ):
        self.material.minimum_stock = Decimal(10001)
        self.material.save(update_fields=["minimum_stock"])
        result = reserve_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=Decimal(10),
            reference=self.item.pk,
            key=uuid.uuid4(),
        )
        consume_reserved(
            owner=self.owner,
            reservation_id=result["reservations"][0],
            quantity=Decimal(3),
            key=uuid.uuid4(),
        )
        movement = self.material.movements.get(quantity=Decimal(-3))
        compensate_movement(
            owner=self.owner,
            movement_id=movement.pk,
            quantity=Decimal(1),
            key=uuid.uuid4(),
            reason="Synthetic return",
        )
        row = stock_levels(self.owner).get(pk=self.material.pk)
        self.assertEqual(row.ledger_physical, self.material.physical_stock)
        self.assertEqual(row.ledger_reserved, self.material.reserved_stock)
        self.assertEqual(row.ledger_available, self.material.available_stock)
        self.assertEqual(
            below_minimum(self.owner)[0]["available"], self.material.available_stock
        )

    def test_report_paginates_preserves_filters_and_exports_all_rows(self):
        for _ in range(26):
            self.make_order(1)
        self.client.force_login(self.owner)
        params = {"status": "waiting", "project": str(self.project.pk), "page": "2"}
        response = self.client.get(reverse("operations:reports"), params)
        self.assertEqual(response.context["page_obj"].paginator.count, 27)
        self.assertEqual(len(response.context["orders"]), 2)
        self.assertContains(response, "project=" + str(self.project.pk))
        params["export"] = "csv"
        exported = self.client.get(reverse("operations:reports"), params)
        self.assertEqual(
            len(
                list(
                    csv.reader(
                        io.StringIO(exported.content.decode("utf-8-sig")), delimiter=";"
                    )
                )
            ),
            28,
        )

    def test_invalid_report_is_not_empty_and_global_unplanned_ignores_status_filter(
        self,
    ):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("operations:reports"), {"start": "2026-11-05", "end": "2026-11-01"}
        )
        self.assertContains(response, "Revise os filtros")
        self.assertNotContains(response, "Nenhum pedido neste período")
        response = self.client.get(
            reverse("production:calendar"), {"status": "completed"}
        )
        self.assertContains(response, "Quadro global")
        self.assertIn(self.order, response.context["unplanned"])

    def test_report_does_not_load_version_pdf_or_snapshots(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("operations:reports"))
        for order in response.context["orders"]:
            self.assertTrue(
                {"pdf", "public_snapshot", "internal_snapshot"}.issubset(
                    order.current_version.get_deferred_fields()
                )
            )
            with self.assertNumQueries(0):
                order.total
                order.balance
