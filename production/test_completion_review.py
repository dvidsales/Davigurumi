import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from finance.models import Payment
from finance.services import record_payment
from projects.services import create_project
from sales.services import create_quote, add_quote_item, publish, decide
from .models import DeliveryEvent
from .services import create_order, record_produced


class CompletionReviewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="review", email="review@example.test"
        )
        project = create_project(
            owner=self.owner,
            name="Olivia",
            estimated_seconds=3600,
            hourly_rate=Decimal("50"),
            percentage=Decimal(0),
        )
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        add_quote_item(
            owner=self.owner, version_id=version.pk, project_id=project.pk, quantity=2
        )
        _, raw = publish(owner=self.owner, version_id=version.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        self.order = create_order(owner=self.owner, version_id=version.pk)
        self.item = self.order.items.get()
        self.client.force_login(self.owner)
        self.path = reverse("production:completion", args=[self.order.pk])

    def payload(self):
        response = self.client.get(self.path)
        form = response.context["form"]
        rows = response.context["rows"]
        return {
            "key": str(form["key"].value()),
            "state": form["state"].value(),
            "complete": "on",
            "amount": str(self.order.balance),
            "date": timezone.localdate().isoformat(),
            "method": "pix",
            "items-TOTAL_FORMS": str(len(rows)),
            "items-INITIAL_FORMS": str(len(rows)),
            "items-0-item_id": str(self.item.pk),
            "items-0-produced": "2",
            "items-0-delivery": "2",
        }

    def test_defaults_balance_and_confirm_only_once(self):
        record_payment(
            owner=self.owner,
            version_id=self.order.current_version_id,
            amount=Decimal("20"),
            date=timezone.localdate(),
            method="cash",
            key=uuid.uuid4(),
        )
        response = self.client.get(self.path)
        self.assertEqual(response.context["form"]["amount"].value(), Decimal("80"))
        self.assertEqual(response.context["form"]["method"].value(), "cash")
        self.assertFalse(response.context["form"]["receive_payment"].value())
        self.assertEqual(response.context["rows"][0]["produced"].value(), 2)
        payment_page = self.client.get(
            reverse("finance:payment", args=[self.order.current_version_id])
        )
        self.assertEqual(payment_page.context["form"]["amount"].value(), Decimal("80"))
        data = self.payload()
        data["receive_payment"] = "on"
        for _ in range(2):
            self.assertRedirects(
                self.client.post(self.path, data),
                reverse("production:detail", args=[self.order.pk]),
            )
        self.item.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual((self.item.produced, self.item.delivered), (2, 2))
        self.assertEqual(self.order.status, "completed")
        self.assertEqual(self.order.balance, 0)
        self.assertEqual(Payment.objects.filter(owner=self.owner).count(), 2)
        self.assertEqual(DeliveryEvent.objects.filter(item=self.item).count(), 1)

    def test_partial_edit_and_no_unconfirmed_payment(self):
        data = self.payload()
        data.pop("complete")
        data["items-0-produced"] = "1"
        data["items-0-delivery"] = "1"
        self.assertEqual(self.client.post(self.path, data).status_code, 302)
        self.item.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual((self.item.produced, self.item.delivered), (1, 1))
        self.assertNotEqual(self.order.status, "completed")
        self.assertFalse(Payment.objects.filter(owner=self.owner).exists())

    def test_invalid_payment_rolls_back_everything_and_preserves_edits(self):
        data = self.payload()
        data.update(receive_payment="on", amount="101")
        response = self.client.post(self.path, data)
        self.assertContains(response, "Valor supera o saldo devido")
        self.assertEqual(response.context["form"]["amount"].value(), "101")
        self.item.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual((self.item.produced, self.item.delivered), (0, 0))
        self.assertEqual(self.order.status, "waiting")
        self.assertFalse(DeliveryEvent.objects.filter(item=self.item).exists())
        self.assertFalse(Payment.objects.filter(owner=self.owner).exists())

    def test_stale_tampered_and_foreign_reviews_rejected(self):
        data = self.payload()
        record_produced(owner=self.owner, item_id=self.item.pk, quantity=1)
        self.assertContains(self.client.post(self.path, data), "O pedido mudou")
        data = self.payload()
        data["state"] += "tampered"
        self.assertContains(
            self.client.post(self.path, data), "expirou ou foi alterada"
        )
        other = get_user_model().objects.create_user(username="other_review")
        data = self.payload()
        data["items-0-item_id"] = str(uuid.uuid4())
        self.assertContains(self.client.post(self.path, data), "lista de peças mudou")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.client.post(self.path, data).status_code, 404)
