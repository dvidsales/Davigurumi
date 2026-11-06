"""Synthetic regression fixtures; Django creates an isolated test database."""

import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from materials.models import Material
from materials.stock import receive_stock, reserve_stock
from projects.services import create_project, add_material
from sales.services import create_quote, add_quote_item, publish, decide
from production.services import create_order
from production.models import ProductionSession, SessionCorrection
from production.costs import cost_summary


class ReadFixture:
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="query-review", email="query@example.test"
        )
        cls.material = Material.objects.create(
            owner=cls.owner, name="Synthetic yarn", kind="yarn", unit="g"
        )
        receive_stock(
            owner=cls.owner,
            material_id=cls.material.pk,
            quantity=Decimal(10000),
            unit_cost=Decimal(".1"),
            key=uuid.uuid4(),
        )
        cls.project = create_project(
            owner=cls.owner,
            name="Synthetic piece",
            estimated_seconds=3600,
            hourly_rate=Decimal(30),
        )
        add_material(
            owner=cls.owner,
            project_id=cls.project.pk,
            material_id=cls.material.pk,
            quantity=Decimal(1),
        )
        cls.order = cls.make_order(1)
        cls.item = cls.order.items.get()

    @classmethod
    def make_order(cls, count):
        quote = create_quote(owner=cls.owner)
        version = quote.versions.get()
        for _ in range(count):
            add_quote_item(
                owner=cls.owner,
                version_id=version.pk,
                project_id=cls.project.pk,
                quantity=1,
            )
        _, token = publish(owner=cls.owner, version_id=version.pk)
        decide(raw=token, action="approve", key=uuid.uuid4(), declaration=True)
        return create_order(owner=cls.owner, version_id=version.pk)


class ReadQueryTests(ReadFixture, TestCase):
    def session(self, seconds=60, active=False):
        now = timezone.now()
        return ProductionSession.objects.create(
            owner=self.owner,
            item=self.item,
            started_at=now - timedelta(seconds=seconds),
            ended_at=None if active else now,
            seconds=seconds,
            hourly_rate=Decimal(30),
        )

    def test_session_queries_are_constant(self):
        counts = []
        for target in (1, 10, 50):
            for _ in range(target - ProductionSession.objects.count()):
                session = self.session()
                SessionCorrection.objects.create(
                    session=session, seconds=120, reason="Synthetic correction"
                )
            with CaptureQueriesContext(connection) as queries:
                sessions = ProductionSession.objects.with_effective_seconds()
                self.assertEqual(
                    sum(s.effective_seconds for s in sessions), target * 120
                )
            counts.append(len(queries))
        print("SESSION_QUERY_COUNTS", counts)
        self.assertEqual(counts, [1, 1, 1])

    def test_correction_fallback_and_timestamp_tie(self):
        session = self.session()
        self.assertEqual(session.effective_seconds, 60)
        first = SessionCorrection.objects.create(
            session=session, seconds=0, reason="Zero"
        )
        self.assertEqual(session.effective_seconds, 0)
        second = SessionCorrection.objects.create(
            session=session, seconds=180, reason="Latest"
        )
        SessionCorrection.objects.filter(pk=second.pk).update(
            created_at=first.created_at
        )
        self.assertEqual(session.effective_seconds, 180)
        with self.assertNumQueries(1):
            loaded = ProductionSession.objects.with_effective_seconds().get(
                pk=session.pk
            )
            self.assertEqual(loaded.effective_seconds, 180)

    def test_cost_queries_do_not_grow_per_item_or_session(self):
        counts = []
        for count in (1, 20):
            order = self.make_order(count)
            for item in order.items.all():
                reserve_stock(
                    owner=self.owner,
                    material_id=self.material.pk,
                    quantity=Decimal(".5"),
                    reference=item.pk,
                    key=uuid.uuid4(),
                )
            with CaptureQueriesContext(connection) as queries:
                result = cost_summary(order)
            counts.append(len(queries))
            self.assertEqual(result["reserved"], Decimal(".05") * count)
        print("ITEM_QUERY_COUNTS", counts)
        self.assertEqual(counts[0], counts[1])
        for _ in range(50):
            session = self.session()
            SessionCorrection.objects.create(
                session=session, seconds=120, reason="Synthetic"
            )
        with CaptureQueriesContext(connection) as queries:
            result = cost_summary(self.order)
        print("COST_50_SESSION_QUERIES", len(queries))
        self.assertLessEqual(len(queries), 9)
        self.assertEqual(result["labor"], Decimal(50))
        self.session(active=True)
        self.assertFalse(cost_summary(self.order)["actual_complete"])

    def test_calendar_queries_are_constant_for_unplanned_orders(self):
        self.client.force_login(self.owner)
        self.client.get(
            "/pedidos/calendario/"
        )  # Warm lazy authentication/template setup.
        counts = []
        for count in (1, 10):
            while self.owner.order_set.count() < count:
                self.make_order(1)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get("/pedidos/calendario/")
            self.assertEqual(response.status_code, 200)
            counts.append(len(queries))
        print("CALENDAR_QUERY_COUNTS", counts)
        self.assertEqual(counts[0], counts[1])

    def test_partial_unknown_and_foreign_reservations_and_retired_item(self):
        from materials.stock import consume_reserved

        result = reserve_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=Decimal(2),
            reference=self.item.pk,
            key=uuid.uuid4(),
        )
        consume_reserved(
            owner=self.owner,
            reservation_id=result["reservations"][0],
            quantity=Decimal(".5"),
            key=uuid.uuid4(),
        )
        unknown = Material.objects.create(
            owner=self.owner, name="Unknown synthetic cost", kind="yarn", unit="g"
        )
        receive_stock(
            owner=self.owner,
            material_id=unknown.pk,
            quantity=Decimal(1),
            unit_cost=None,
            key=uuid.uuid4(),
        )
        reserve_stock(
            owner=self.owner,
            material_id=unknown.pk,
            quantity=Decimal(1),
            reference=self.item.pk,
            key=uuid.uuid4(),
        )
        foreign = get_user_model().objects.create_user(
            username="foreign-reservation", email="foreign-reservation@example.test"
        )
        material = Material.objects.create(
            owner=foreign, name="Foreign synthetic yarn", kind="yarn", unit="g"
        )
        receive_stock(
            owner=foreign,
            material_id=material.pk,
            quantity=Decimal(1),
            unit_cost=Decimal(999),
            key=uuid.uuid4(),
        )
        reserve_stock(
            owner=foreign,
            material_id=material.pk,
            quantity=Decimal(1),
            reference=self.item.pk,
            key=uuid.uuid4(),
        )
        self.item.retired = True
        self.item.save(update_fields=["retired"])
        result = cost_summary(self.order)
        self.assertEqual(result["estimate"], Decimal(0))
        self.assertEqual(result["reserved"], Decimal(".15"))
        self.assertFalse(result["reserved_complete"])

    def test_order_detail_queries_do_not_grow_per_session(self):
        from django.urls import reverse

        self.client.force_login(self.owner)
        url = reverse("production:detail", args=[self.order.pk])
        counts = []
        for target in (1, 50):
            for _ in range(target - ProductionSession.objects.count()):
                self.session()
            self.client.get(url)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            counts.append(len(queries))
        print("ORDER_DETAIL_QUERY_COUNTS", counts)
        self.assertEqual(counts[0], counts[1])
