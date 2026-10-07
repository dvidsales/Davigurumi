import uuid
from decimal import Decimal as D
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.http import Http404
from django.test import TestCase
from django.urls import reverse
from .models import Material, StockMovement
from .stock import receive_stock, reserve_stock, consume_available, compensate_movement
from .services import archive_material


class CompensationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="compensator", email="compensator@example.test"
        )
        self.other = get_user_model().objects.create_user(
            username="compensator_other", email="compensator_other@example.test"
        )
        self.material = Material.objects.create(
            owner=self.owner, name="Fio", kind="yarn", unit="g"
        )
        result = receive_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("100"),
            unit_cost=D(".2"),
            key=uuid.uuid4(),
        )
        self.origin = StockMovement.objects.get(pk=result["movement"])

    def test_partial_return_of_receipt_keeps_original_and_reserved_stock(self):
        reserve_stock(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("40"),
            key=uuid.uuid4(),
        )
        key = uuid.uuid4()
        kwargs = dict(
            owner=self.owner,
            movement_id=self.origin.pk,
            quantity=D("30"),
            key=key,
            reason="Devolvido ao fornecedor",
        )
        result = compensate_movement(**kwargs)
        self.assertEqual(compensate_movement(**kwargs), result)
        self.origin.refresh_from_db()
        self.assertEqual(self.origin.quantity, D("100"))
        self.assertEqual(self.material.physical_stock, D("70"))
        self.assertEqual(self.material.reserved_stock, D("40"))
        compensation = StockMovement.objects.get(pk=result["movement"])
        self.assertEqual(compensation.reverses, self.origin)
        self.assertEqual(compensation.unit_cost, D(".2"))
        with self.assertRaises(ValidationError):
            compensate_movement(
                owner=self.owner,
                movement_id=self.origin.pk,
                quantity=D("31"),
                key=uuid.uuid4(),
                reason="Saldo reservado",
            )
        self.assertEqual(self.material.physical_stock, D("70"))

    def test_recovery_cannot_exceed_consumption_or_compensate_a_compensation(self):
        result = consume_available(
            owner=self.owner,
            material_id=self.material.pk,
            quantity=D("60"),
            key=uuid.uuid4(),
            reason="Trabalho",
        )
        movement = StockMovement.objects.get(pk=result["movements"][0])
        returned = compensate_movement(
            owner=self.owner,
            movement_id=movement.pk,
            quantity=D("25"),
            key=uuid.uuid4(),
            reason="Sobra recuperada",
        )
        self.assertEqual(self.material.physical_stock, D("65"))
        with self.assertRaises(ValidationError):
            compensate_movement(
                owner=self.owner,
                movement_id=movement.pk,
                quantity=D("36"),
                key=uuid.uuid4(),
                reason="Excesso",
            )
        with self.assertRaises(ValidationError):
            compensate_movement(
                owner=self.owner,
                movement_id=returned["movement"],
                quantity=D("1"),
                key=uuid.uuid4(),
                reason="Cadeia",
            )
        from django.core.management import call_command

        call_command("reconcile_stock")

    def test_foreign_owner_cannot_read_or_compensate_origin(self):
        with self.assertRaises(Http404):
            compensate_movement(
                owner=self.other,
                movement_id=self.origin.pk,
                quantity=D("1"),
                key=uuid.uuid4(),
                reason="Invasão",
            )
        self.client.force_login(self.other)
        url = reverse("materials:compensation", args=[self.origin.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_archive_is_reversible_idempotent_and_preserves_existing_references(self):
        from projects.services import create_project, add_material
        from purchasing.models import Purchase
        from purchasing.services import add_item
        from django.utils import timezone
        from operations.models import AuditEvent

        project = create_project(owner=self.owner, name="Peça")
        line = add_material(
            owner=self.owner,
            project_id=project.pk,
            material_id=self.material.pk,
            quantity=D("5"),
        )
        kwargs = dict(
            owner=self.owner,
            material_id=self.material.pk,
            archived=True,
            reason="Fora de catálogo",
            key=uuid.uuid4(),
        )
        archive_material(**kwargs)
        archive_material(**kwargs)
        self.assertEqual(self.material.physical_stock, D("100"))
        self.assertEqual(
            AuditEvent.objects.filter(action="material_archived").count(), 1
        )
        self.assertTrue(line.revision.materials.filter(material=self.material).exists())
        self.client.force_login(self.owner)
        self.assertNotContains(
            self.client.get(reverse("materials:index")), self.material.name
        )
        self.assertContains(
            self.client.get(reverse("materials:index"), {"state": "archived"}),
            self.material.name,
        )
        self.assertEqual(
            self.client.get(
                reverse("materials:archive", args=[self.material.pk])
            ).status_code,
            405,
        )
        purchase = Purchase.objects.create(owner=self.owner, date=timezone.localdate())
        with self.assertRaises(Http404):
            add_item(
                owner=self.owner,
                purchase_id=purchase.pk,
                material_id=self.material.pk,
                quantity=D("1"),
                unit_price=D("1"),
            )
        archive_material(
            owner=self.owner,
            material_id=self.material.pk,
            archived=False,
            reason="Voltou ao catálogo",
            key=uuid.uuid4(),
        )
        add_item(
            owner=self.owner,
            purchase_id=purchase.pk,
            material_id=self.material.pk,
            quantity=D("1"),
            unit_price=D("1"),
        )

    def test_postgres_rejects_cross_material_compensation_and_ledger_deletion(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL trigger")
        foreign = Material.objects.create(
            owner=self.other, name="Privado", kind="yarn", unit="g"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.create(
                material=foreign,
                quantity=D("-1"),
                unit_cost=D(".2"),
                kind="adjustment",
                reverses=self.origin,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.filter(pk=self.origin.pk).delete()
