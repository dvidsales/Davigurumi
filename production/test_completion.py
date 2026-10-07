import uuid
from decimal import Decimal as D
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.http import Http404
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from . import tests as production_fixtures
from .services import consume_item, record_expense, reserve_order
from .models import Consumption, ActualExpense
from .costs import cost_summary
from materials.stock import compensate_movement


class CompletionTests(TestCase):
    setUp = production_fixtures.ProductionTests.setUp

    def test_recovered_order_stock_reduces_cost_and_remaining_need_uses_net_consumption(
        self,
    ):
        result = consume_item(
            owner=self.owner,
            item_id=self.item.pk,
            material_id=self.material.pk,
            quantity=D("100"),
            key=uuid.uuid4(),
        )
        movement = result["movements"][0]
        with self.assertRaises(ValidationError):
            compensate_movement(
                owner=self.owner,
                movement_id=movement,
                quantity=D("20"),
                key=uuid.uuid4(),
                reason="Fluxo indevido",
            )
        compensate_movement(
            owner=self.owner,
            movement_id=movement,
            item_id=self.item.pk,
            quantity=D("20"),
            key=uuid.uuid4(),
            reason="Sobra física",
        )
        costs = cost_summary(self.order)
        self.assertEqual(costs["materials"], D("8"))
        self.assertEqual(self.material.physical_stock, D("428"))
        reserve_order(owner=self.owner, order_id=self.order.pk, key=uuid.uuid4())
        self.assertEqual(self.material.reserved_stock, D("160"))
        other = get_user_model().objects.create_user(
            username="foreign_recover", email="foreign_recover@example.test"
        )
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(
                reverse("production:recover", args=[Consumption.objects.get().pk])
            ).status_code,
            404,
        )

    def test_actual_expense_reversals_preserve_history_and_result(self):
        kwargs = dict(
            owner=self.owner,
            order_id=self.order.pk,
            amount=D("10"),
            date=timezone.localdate(),
            description="Envio",
            key=uuid.uuid4(),
        )
        result = record_expense(**kwargs)
        self.assertEqual(record_expense(**kwargs), result)
        self.assertEqual(cost_summary(self.order)["expenses"], D("10"))
        record_expense(
            owner=self.owner,
            order_id=self.order.pk,
            amount=D("10"),
            date=timezone.localdate(),
            description="Despesa duplicada revertida",
            key=uuid.uuid4(),
            reverses=result["expense"],
        )
        self.assertEqual(cost_summary(self.order)["expenses"], D("0"))
        self.assertEqual(ActualExpense.objects.count(), 2)
        self.assertEqual(
            ActualExpense.objects.get(pk=result["expense"]).amount, D("10")
        )
        with self.assertRaises(ValidationError):
            record_expense(
                owner=self.owner,
                order_id=self.order.pk,
                amount=D("10"),
                date=timezone.localdate(),
                description="Outra reversão",
                key=uuid.uuid4(),
                reverses=result["expense"],
            )

    def test_foreign_expense_order_and_form_are_rejected(self):
        other = get_user_model().objects.create_user(
            username="foreign_expense", email="foreign_expense@example.test"
        )
        with self.assertRaises(Http404):
            record_expense(
                owner=other,
                order_id=self.order.pk,
                amount=D("1"),
                date=timezone.localdate(),
                description="Invasão",
                key=uuid.uuid4(),
            )
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(
                reverse("production:expense", args=[self.order.pk])
            ).status_code,
            404,
        )

    def test_postgres_expense_history_is_append_only(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL trigger")
        result = record_expense(
            owner=self.owner,
            order_id=self.order.pk,
            amount=D("1"),
            date=timezone.localdate(),
            description="Envio",
            key=uuid.uuid4(),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ActualExpense.objects.filter(pk=result["expense"]).update(
                description="Apagado"
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ActualExpense.objects.filter(pk=result["expense"]).delete()

    def make_amendment(self, remove=False):
        from sales.services import (
            new_version,
            edit_draft_item,
            remove_draft_item,
            add_quote_item,
            publish,
            decide,
        )
        from projects.services import create_project

        amendment = new_version(owner=self.owner, quote_id=self.quote.pk)
        if remove:
            remove_draft_item(owner=self.owner, item_id=amendment.items.get().pk)
            project = create_project(
                owner=self.owner,
                name="Peça substituta",
                estimated_seconds=3600,
                hourly_rate=D("30"),
            )
            add_quote_item(
                owner=self.owner,
                version_id=amendment.pk,
                project_id=project.pk,
                quantity=1,
            )
        else:
            source = amendment.items.get()
            edit_draft_item(
                owner=self.owner,
                item_id=source.pk,
                project_id=source.project_revision.project_id,
                quantity=3,
            )
        _, raw = publish(owner=self.owner, version_id=amendment.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        return amendment

    def test_amendment_releases_reservations_and_retires_unproduced_item_without_deleting_it(
        self,
    ):
        from .services import apply_amendment, start_session

        reserve_order(owner=self.owner, order_id=self.order.pk, key=uuid.uuid4())
        amendment = self.make_amendment(remove=True)
        apply_amendment(
            owner=self.owner, order_id=self.order.pk, version_id=amendment.pk
        )
        self.item.refresh_from_db()
        self.assertTrue(self.item.retired)
        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.material.reserved_stock, 0)
        self.assertEqual(self.material.physical_stock, D("508"))
        with self.assertRaises(Http404):
            start_session(owner=self.owner, item_id=self.item.pk)

    def test_consumed_material_change_requires_reconciliation_and_keeps_spent_cost(
        self,
    ):
        from .services import apply_amendment

        consume_item(
            owner=self.owner,
            item_id=self.item.pk,
            material_id=self.material.pk,
            quantity=D("50"),
            key=uuid.uuid4(),
        )
        amendment = self.make_amendment(remove=True)
        with self.assertRaises(ValidationError):
            apply_amendment(
                owner=self.owner, order_id=self.order.pk, version_id=amendment.pk
            )
        self.item.refresh_from_db()
        self.assertFalse(self.item.retired)
        apply_amendment(
            owner=self.owner,
            order_id=self.order.pk,
            version_id=amendment.pk,
            reconciliation_reason="Material já usado não recuperável; custo preservado",
        )
        self.assertEqual(cost_summary(self.order)["materials"], D("5"))
        self.assertEqual(self.material.physical_stock, D("458"))

    def test_produced_item_cannot_be_removed_by_an_amendment(self):
        from .services import apply_amendment, record_produced

        record_produced(owner=self.owner, item_id=self.item.pk, quantity=1)
        amendment = self.make_amendment(remove=True)
        with self.assertRaises(ValidationError):
            apply_amendment(
                owner=self.owner,
                order_id=self.order.pk,
                version_id=amendment.pk,
                reconciliation_reason="Não deve permitir",
            )
        self.item.refresh_from_db()
        self.assertFalse(self.item.retired)

    def test_calendar_and_comparison_are_private_and_do_not_mix_quotes(self):
        from datetime import timedelta

        self.order.planned_start = timezone.localdate()
        self.order.production_due = timezone.localdate() + timedelta(days=2)
        self.order.save()
        self.client.force_login(self.owner)
        calendar = self.client.get(reverse("production:calendar"))
        self.assertContains(calendar, "Início planejado")
        amendment = self.make_amendment()
        compare = self.client.get(
            reverse("sales:compare", args=[self.quote.pk]),
            {"before": self.version.pk, "after": amendment.pk},
        )
        self.assertContains(compare, "Alterado")
        other = get_user_model().objects.create_user(
            username="foreign_calendar", email="foreign_calendar@example.test"
        )
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(reverse("sales:compare", args=[self.quote.pk])).status_code,
            404,
        )
        self.assertEqual(
            len(self.client.get(reverse("production:calendar")).context["days"]), 0
        )
