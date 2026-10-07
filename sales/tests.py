import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction, connection, close_old_connections
from django.http import Http404
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from materials.models import Material
from operations.models import Notification
from projects.services import create_project, add_material
from .models import QuoteVersion, QuoteItem, QuoteEvent, Client
from .services import (
    create_quote,
    add_quote_item,
    publish,
    new_version,
    decide,
    reissue_token,
    get_token,
)

D = Decimal


class QuoteTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="seller", email="seller@example.test", first_name="Artesã"
        )
        self.material = Material.objects.create(
            owner=self.owner,
            name="MATERIAL PRIVADO",
            kind="yarn",
            unit="g",
            notes="NOTA SECRETA",
        )
        self.project = create_project(
            owner=self.owner, name="Boneco", estimated_seconds=3600, hourly_rate=D("30")
        )
        add_material(
            owner=self.owner,
            project_id=self.project.pk,
            material_id=self.material.pk,
            quantity=D("100"),
            manual_unit_cost=D(".1"),
        )
        self.quote = create_quote(owner=self.owner)
        self.version = self.quote.versions.get()
        self.item = add_quote_item(
            owner=self.owner,
            version_id=self.version.pk,
            project_id=self.project.pk,
            quantity=1,
        )

    def publication(self):
        return publish(owner=self.owner, version_id=self.version.pk)

    def test_publication_snapshot_and_pdf_survive_material_and_account_edits(self):
        version, raw = self.publication()
        original = version.public_snapshot.copy()
        pdf = bytes(version.pdf)
        self.material.name = "Mudou"
        self.material.save()
        self.owner.first_name = "Mudou também"
        self.owner.save()
        version.refresh_from_db()
        self.assertEqual(version.public_snapshot, original)
        self.assertEqual(bytes(version.pdf), pdf)
        self.assertEqual(version.total, D("60.00"))

    def test_portal_and_pdf_do_not_expose_private_fields_and_get_never_approves(self):
        version, raw = self.publication()
        response = self.client.get(reverse("sales:portal", args=[raw]))
        self.assertEqual(response.status_code, 200)
        for private in (
            "MATERIAL PRIVADO",
            "NOTA SECRETA",
            "unit_cost",
            "internal_snapshot",
            "margin",
        ):
            self.assertNotContains(response, private)
            self.assertNotIn(private.encode(), bytes(version.pdf))
        version.refresh_from_db()
        self.assertEqual(version.status, "sent")
        self.assertEqual(response["Referrer-Policy"], "same-origin")

    def test_approval_is_idempotent_and_notifications_are_not_duplicated(self):
        version, raw = self.publication()
        key = uuid.uuid4()
        decide(raw=raw, action="approve", key=key, declaration=True)
        decide(raw=raw, action="approve", key=key, declaration=True)
        self.assertEqual(QuoteEvent.objects.filter(kind="approve").count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        version.refresh_from_db()
        self.assertEqual(version.approved_hash, version.content_hash)
        with self.assertRaises(ValidationError):
            decide(raw=raw, action="decline", key=uuid.uuid4(), declaration=True)

    def test_old_version_cannot_be_approved_after_v2_published(self):
        version, raw = self.publication()
        latest = new_version(owner=self.owner, quote_id=self.quote.pk)
        publish(owner=self.owner, version_id=latest.pk)
        with self.assertRaises(ValidationError):
            decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        version.refresh_from_db()
        self.assertEqual(version.status, "superseded")

    def test_reissued_token_revokes_previous(self):
        version, raw = self.publication()
        new = reissue_token(owner=self.owner, version_id=version.pk)
        with self.assertRaises(Http404):
            get_token(raw)
        self.assertEqual(get_token(new).version_id, version.pk)

    def test_unknown_cost_blocks_without_explicit_manual_price(self):
        project = create_project(owner=self.owner, name="Sem custo")
        add_material(
            owner=self.owner,
            project_id=project.pk,
            material_id=self.material.pk,
            quantity=D("1"),
        )
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        add_quote_item(
            owner=self.owner, version_id=version.pk, project_id=project.pk, quantity=1
        )
        with self.assertRaises(ValidationError):
            publish(owner=self.owner, version_id=version.pk, confirm_limitations=True)

    def test_database_guards_block_cross_owner_links_and_published_edits(self):
        if connection.vendor != "postgresql":
            self.skipTest("Database guards use PostgreSQL triggers.")
        other = get_user_model().objects.create_user(
            username="other", email="other@example.test"
        )
        client = Client.objects.create(owner=other, name="Privado")
        with self.assertRaises(IntegrityError), transaction.atomic():
            from .models import Quote

            Quote.objects.filter(pk=self.quote.pk).update(client=client)
        version, _ = self.publication()
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuoteVersion.objects.filter(pk=version.pk).update(total=D("1"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuoteItem.objects.filter(pk=self.item.pk).update(description="Alterado")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.item.delete()


class ConcurrentApprovalTests(TransactionTestCase):
    def test_opposing_decisions_cannot_both_win(self):
        if connection.vendor != "postgresql":
            self.skipTest("Real concurrency requires PostgreSQL.")
        owner = get_user_model().objects.create_user(
            username="simultaneous", email="simultaneous@example.test"
        )
        project = create_project(
            owner=owner, name="Peça", estimated_seconds=3600, hourly_rate=D("30")
        )
        quote = create_quote(owner=owner)
        version = quote.versions.get()
        add_quote_item(
            owner=owner, version_id=version.pk, project_id=project.pk, quantity=1
        )
        _, raw = publish(owner=owner, version_id=version.pk)
        barrier = Barrier(2)

        def worker(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                decide(raw=raw, action=action, key=uuid.uuid4(), declaration=True)
                return "accepted"
            except ValidationError:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, ["approve", "decline"]))
        self.assertCountEqual(results, ["accepted", "rejected"])
        self.assertEqual(
            QuoteEvent.objects.filter(
                version=version, kind__in=["approve", "decline"]
            ).count(),
            1,
        )
