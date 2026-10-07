import uuid
from decimal import Decimal
from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from materials.models import Material, StockReservation
from materials.stock import receive_stock
from projects.services import create_project, add_material
from sales.services import create_quote, add_quote_item, publish, decide
from .models import ProductionSession, Consumption
from .services import (
    create_order,
    reserve_order,
    consume_item,
    close_order,
    start_session,
    stop_session,
    manual_time,
    correct_time,
    record_produced,
    deliver_item,
)

D = Decimal


class ProductionTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="producer", email="producer@example.test"
        )
        self.material = Material.objects.create(
            owner=self.owner, name="Fio", kind="yarn", unit="g"
        )
        receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("508"),
            unit_cost=D(".1"),
            key=uuid.uuid4(),
        )
        project = create_project(
            owner=self.owner, name="Peça", estimated_seconds=3600, hourly_rate=D("30")
        )
        add_material(
            owner=self.owner,
            project_id=project.pk,
            material_id=self.material.pk,
            quantity=D("120"),
        )
        self.quote = create_quote(owner=self.owner)
        self.version = self.quote.versions.get()
        add_quote_item(
            owner=self.owner,
            version_id=self.version.pk,
            project_id=project.pk,
            quantity=2,
        )
        _, raw = publish(owner=self.owner, version_id=self.version.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        self.order = create_order(owner=self.owner, version_id=self.version.pk)
        self.item = self.order.items.get()

    def test_order_conversion_is_idempotent_and_does_not_start_or_consume(self):
        again = create_order(owner=self.owner, version_id=self.version.pk)
        self.assertEqual(again.pk, self.order.pk)
        self.assertEqual(self.order.status, "waiting")
        self.assertEqual(self.material.physical_stock, D("508"))

    def test_cancel_after_partial_consumption_preserves_usage_and_releases_remaining(
        self,
    ):
        reserve_order(owner=self.owner, order_id=self.order.pk, key=uuid.uuid4())
        reservation = StockReservation.objects.get(reference=self.item.pk)
        consume_item(
            owner=self.owner,
            item_id=self.item.pk,
            material_id=self.material.pk,
            quantity=D("50"),
            reservation_id=reservation.pk,
            key=uuid.uuid4(),
        )
        close_order(owner=self.owner, order_id=self.order.pk, status="cancelled")
        self.assertEqual(self.material.physical_stock, D("458"))
        self.assertEqual(self.material.reserved_stock, 0)
        self.assertEqual(Consumption.objects.count(), 1)

    def test_timer_recovers_same_session_and_does_not_consume(self):
        session = start_session(owner=self.owner, item_id=self.item.pk)
        self.assertEqual(
            start_session(owner=self.owner, item_id=self.item.pk).pk, session.pk
        )
        self.assertEqual(ProductionSession.objects.count(), 1)
        self.assertEqual(self.material.physical_stock, D("508"))
        with patch(
            "production.services.timezone.now",
            return_value=session.started_at + timedelta(seconds=65),
        ):
            ended = stop_session(owner=self.owner, session_id=session.pk)
        self.assertEqual(ended.seconds, 65)
        correct_time(
            owner=self.owner,
            session_id=session.pk,
            seconds=60,
            reason="Pausa não registrada",
        )
        ended.refresh_from_db()
        self.assertEqual(ended.seconds, 65)
        self.assertEqual(ended.effective_seconds, 60)

    def test_manual_session_overlap_is_rejected(self):
        manual_time(owner=self.owner, item_id=self.item.pk, seconds=60)
        with self.assertRaises(ValidationError):
            manual_time(owner=self.owner, item_id=self.item.pk, seconds=60)

    def test_partial_delivery_and_production_completion_are_independent(self):
        record_produced(owner=self.owner, item_id=self.item.pk, quantity=1)
        key = uuid.uuid4()
        first = deliver_item(
            owner=self.owner, item_id=self.item.pk, quantity=1, key=key
        )
        self.assertEqual(
            deliver_item(owner=self.owner, item_id=self.item.pk, quantity=1, key=key),
            first,
        )
        with self.assertRaises(ValidationError):
            close_order(owner=self.owner, order_id=self.order.pk, status="completed")
        record_produced(owner=self.owner, item_id=self.item.pk, quantity=2)
        close_order(owner=self.owner, order_id=self.order.pk, status="completed")
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.delivery_status, "delivered")
        self.assertGreater(self.order.balance, 0)
        deliver_item(
            owner=self.owner, item_id=self.item.pk, quantity=1, key=uuid.uuid4()
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.delivery_status, "delivered")

    def test_actual_material_cost_uses_consumed_layer_not_updated_reference(self):
        from .costs import cost_summary

        reserve_order(owner=self.owner, order_id=self.order.pk, key=uuid.uuid4())
        reservation = StockReservation.objects.get(reference=self.item.pk)
        consume_item(
            owner=self.owner,
            item_id=self.item.pk,
            material_id=self.material.pk,
            quantity=D("50"),
            reservation_id=reservation.pk,
            key=uuid.uuid4(),
        )
        receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("100"),
            unit_cost=D(".9"),
            key=uuid.uuid4(),
        )
        costs = cost_summary(self.order)
        self.assertEqual(costs["materials"], D("5.00"))
        self.assertEqual(costs["reserved"], D("19.00"))
        self.assertEqual(costs["estimate"], D("84.00"))
