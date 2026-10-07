from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from sales.models import Client, Quote
from sales.services import create_quote
from purchasing.models import Purchase, Supplier


class WorkflowFeedbackTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="feedback", email="feedback@example.test"
        )
        self.other = get_user_model().objects.create_user(
            username="feedback_other", email="feedback_other@example.test"
        )
        self.client.force_login(self.owner)

    def test_client_created_inside_quote_and_searchable_by_id(self):
        response = self.client.post(
            reverse("sales:create"),
            {
                "new_client_name": "Cliente de teste",
                "new_client_contact": "Contato fictício",
                "valid_days": 15,
            },
        )
        self.assertEqual(response.status_code, 302)
        contact = Client.objects.get(owner=self.owner)
        self.assertEqual(Quote.objects.get(owner=self.owner).client_id, contact.pk)
        self.assertContains(
            self.client.get(reverse("sales:clients"), {"q": str(contact.pk)}),
            contact.name,
        )
        self.assertContains(
            self.client.get(reverse("sales:client_history", args=[contact.pk])),
            "Orçamento 1",
        )
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(
                reverse("sales:client_history", args=[contact.pk])
            ).status_code,
            404,
        )

    def test_supplier_created_inside_purchase_and_transaction_rolls_back_on_errors(
        self,
    ):
        path = reverse("purchasing:create")
        response = self.client.post(
            path,
            {
                "new_supplier_name": "Fornecedor de teste",
                "date": "invalid",
                "freight": 0,
                "discount": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Supplier.objects.exists())
        response = self.client.post(
            path,
            {
                "new_supplier_name": "Fornecedor de teste",
                "new_supplier_contact": "Contato fictício",
                "date": "2026-10-07",
                "freight": 0,
                "discount": 0,
            },
        )
        self.assertEqual(response.status_code, 302)
        supplier = Supplier.objects.get(owner=self.owner)
        self.assertEqual(Purchase.objects.get().supplier_id, supplier.pk)
        self.assertContains(
            self.client.get(reverse("purchasing:supplier_history", args=[supplier.pk])),
            "Fornecedor de teste",
        )
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(
                reverse("purchasing:supplier_history", args=[supplier.pk])
            ).status_code,
            404,
        )

    def test_foreign_contact_and_duplicate_registration_rejected(self):
        foreign = Client.objects.create(
            owner=self.other, name="Private", contact="Private"
        )
        response = self.client.post(
            reverse("sales:create"), {"client": foreign.pk, "valid_days": 15}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Quote.objects.exists())
        local = Client.objects.create(owner=self.owner, name="Local")
        response = self.client.get(reverse("sales:create"), {"contact_q": "Local"})
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, str(local.pk))
        self.assertNotContains(response, str(foreign.pk))
        response = self.client.post(
            reverse("sales:create"), {"new_client_name": "Local", "valid_days": 15}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Client.objects.filter(owner=self.owner).count(), 1)

    def test_empty_quote_guides_to_piece_instead_of_publication(self):
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        response = self.client.get(reverse("sales:detail", args=[quote.pk]))
        self.assertContains(response, "Adicionar primeira peça")
        self.assertNotContains(
            response, 'href="' + reverse("sales:publish", args=[version.pk]) + '"'
        )
        self.assertRedirects(
            self.client.get(reverse("sales:publish", args=[version.pk])),
            reverse("sales:item", args=[version.pk]),
        )
        version.refresh_from_db()
        self.assertIsNone(version.published_at)
        self.assertEqual(
            self.client.get(
                reverse("projects:create"), {"next_version": version.pk}
            ).status_code,
            200,
        )
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(
                reverse("projects:create"), {"next_version": version.pk}
            ).status_code,
            404,
        )

    def test_link_approval_can_be_converted_from_production_tab(self):
        import uuid
        from decimal import Decimal
        from projects.services import create_project
        from sales.services import add_quote_item, publish, decide
        from production.models import Order

        project = create_project(
            owner=self.owner,
            name="Peça aprovada",
            estimated_seconds=3600,
            hourly_rate=Decimal("30"),
        )
        quote = create_quote(owner=self.owner)
        version = quote.versions.get()
        add_quote_item(
            owner=self.owner, version_id=version.pk, project_id=project.pk, quantity=1
        )
        _, raw = publish(owner=self.owner, version_id=version.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        self.assertIn(
            version,
            self.client.get(reverse("production:index")).context["approved_quotes"],
        )
        from finance.models import Payment

        self.assertFalse(Order.objects.filter(owner=self.owner).exists())
        self.assertFalse(Payment.objects.filter(owner=self.owner).exists())
        self.client.force_login(self.other)
        for path in ("production:index", "finance:index"):
            self.assertEqual(
                list(self.client.get(reverse(path)).context["approved_quotes"]), []
            )
        self.client.force_login(self.owner)
        response = self.client.post(reverse("production:convert", args=[version.pk]))
        order = Order.objects.get(owner=self.owner)
        self.assertRedirects(response, reverse("production:detail", args=[order.pk]))
        self.assertNotIn(
            version,
            self.client.get(reverse("production:index")).context["approved_quotes"],
        )
        self.assertIn(
            version,
            self.client.get(reverse("finance:index")).context["approved_quotes"],
        )
