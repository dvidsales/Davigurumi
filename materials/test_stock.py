import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, close_old_connections
from django.http import Http404
from django.test import TestCase, TransactionTestCase
from .models import Material, StockMovement, CostLayer, StockReservation
from .stock import (
    receive_stock,
    reserve_stock,
    consume_reserved,
    release_reservation,
    consume_available,
    add_conversion,
    reference_cost,
)

D = Decimal


class StockTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="stock", email="stock@example.test"
        )
        self.other = get_user_model().objects.create_user(
            username="other", email="other@example.test"
        )
        self.material = Material.objects.create(
            owner=self.owner, name="Fio", kind="yarn", unit="g"
        )

    def receive(self, qty="508", cost=".1", **kwargs):
        return receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D(qty),
            unit_cost=D(cost) if cost is not None else None,
            key=uuid.uuid4(),
            **kwargs
        )

    def test_reference_prd_reserved_consumption_and_release(self):
        self.receive()
        result = reserve_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("120"),
            key=uuid.uuid4(),
        )
        self.assertEqual(self.material.physical_stock, D("508"))
        self.assertEqual(self.material.available_stock, D("388"))
        consume_reserved(
            owner=self.owner,
            reservation_id=result["reservations"][0],
            quantity=D("50"),
            key=uuid.uuid4(),
        )
        self.assertEqual(self.material.physical_stock, D("458"))
        self.assertEqual(self.material.reserved_stock, D("70"))
        self.assertEqual(self.material.available_stock, D("388"))
        release_reservation(
            owner=self.owner, reservation_id=result["reservations"][0], key=uuid.uuid4()
        )
        self.assertEqual(self.material.available_stock, D("458"))

    def test_custom_conversion_is_frozen_in_history(self):
        add_conversion(
            owner=self.owner,
            material_id=self.material.pk,
            name="novelo",
            factor=D("254"),
        )
        result = self.receive("3", unit="novelo")
        movement = StockMovement.objects.get(pk=result["movement"])
        self.assertEqual(movement.quantity, D("762"))
        add_conversion(
            owner=self.owner,
            material_id=self.material.pk,
            name="novelo",
            factor=D("200"),
        )
        movement.refresh_from_db()
        self.assertEqual(movement.conversion_snapshot["factor"], "254.000000")
        self.assertEqual(movement.quantity, D("762"))

    def test_layers_estimates_and_actual_fifo_cost(self):
        self.receive("100", ".10", lot="mesmo lote")
        self.receive("100", ".20", lot="mesmo lote")
        self.assertEqual(self.material.layers.count(), 2)
        self.assertEqual(reference_cost(self.material, "oldest") * 120, D("12"))
        self.assertEqual(reference_cost(self.material, "newest") * 120, D("24"))
        self.assertEqual(reference_cost(self.material) * 120, D("18"))
        result = consume_available(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("120"),
            key=uuid.uuid4(),
        )
        self.assertEqual(D(result["cost"]), D("14"))
        self.assertEqual(self.material.physical_stock, D("80"))

    def test_insufficient_stock_rolls_back_and_retry_is_idempotent(self):
        key = uuid.uuid4()
        first = receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("100"),
            unit_cost=None,
            key=key,
        )
        second = receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("100"),
            unit_cost=None,
            key=key,
        )
        self.assertEqual(first, second)
        self.assertEqual(self.material.physical_stock, D("100"))
        with self.assertRaises(ValidationError):
            reserve_stock(
                owner=self.owner,
                material_id=self.material.pk,
                quantity=D("101"),
                key=uuid.uuid4(),
            )
        self.assertFalse(StockReservation.objects.exists())
        self.assertEqual(self.material.reserved_stock, 0)

    def test_key_cannot_be_reused_with_changed_payload(self):
        key = uuid.uuid4()
        receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("10"),
            unit_cost=None,
            key=key,
        )
        with self.assertRaises(ValidationError):
            receive_stock(
                owner=self.owner,
                material_id=self.material.pk,
                quantity=D("20"),
                unit_cost=None,
                key=key,
            )

    def test_reference_unknown_cost_is_not_zero(self):
        self.receive("100", None)
        self.assertIsNone(reference_cost(self.material))

    def test_other_owner_cannot_mutate_or_convert(self):
        with self.assertRaises(Http404):
            receive_stock(
                owner=self.other,
                material_id=self.material.pk,
                quantity=D("1"),
                unit_cost=None,
                key=uuid.uuid4(),
            )
        with self.assertRaises(Http404):
            add_conversion(
                owner=self.other,
                material_id=self.material.pk,
                name="novelo",
                factor=D("254"),
            )

    def test_reservations_cannot_be_consumed_as_available_stock(self):
        self.receive("100")
        reserve_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("80"),
            key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            consume_available(
                owner=self.owner,
                material_id=self.material.pk,
                quantity=D("21"),
                key=uuid.uuid4(),
            )
        self.assertEqual(self.material.physical_stock, 100)

    def test_reconcile_ledger_and_layers(self):
        self.receive()
        consume_available(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("10"),
            key=uuid.uuid4(),
        )
        self.assertEqual(
            self.material.physical_stock,
            sum(layer.physical for layer in self.material.layers.all()),
        )


class ConcurrentStockTests(TransactionTestCase):
    def test_two_reservations_cannot_overbook_postgres(self):
        if connection.vendor != "postgresql":
            self.skipTest("Row-lock concurrency requires PostgreSQL.")
        owner = get_user_model().objects.create_user(
            username="concurrent", email="concurrent@example.test"
        )
        material = Material.objects.create(
            owner=owner, name="Fio", kind="yarn", unit="g"
        )
        receive_stock(
            owner=owner,
            material_id=material.pk,
            quantity=D("100"),
            unit_cost=D(".1"),
            key=uuid.uuid4(),
        )
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=owner.pk)
                barrier.wait(timeout=10)
                reserve_stock(
                    owner=user,
                    material_id=material.pk,
                    quantity=D("80"),
                    key=uuid.uuid4(),
                )
                return "accepted"
            except ValidationError:
                return "insufficient"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertCountEqual(results, ["accepted", "insufficient"])
        self.assertEqual(material.reserved_stock, D("80"))
        self.assertEqual(material.available_stock, D("20"))
