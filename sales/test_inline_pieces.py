from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from projects.models import Project
from projects.services import create_project
from sales.models import QuoteItem
from sales.services import create_quote, add_quote_item, publish
from django.core.exceptions import ValidationError


class InlinePieceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="inline", email="inline@example.test"
        )
        self.client.force_login(self.owner)
        self.quote = create_quote(owner=self.owner)
        self.version = self.quote.versions.get()
        self.path = reverse("sales:item", args=[self.version.pk])

    def test_inline_creation_reusable_price_and_unknown_cost(self):
        response = self.client.post(
            self.path,
            {
                "new_piece_name": "Olivia",
                "quantity": 2,
                "manual_price": "80",
                "discount": 0,
                "fixed_discount": 0,
            },
        )
        self.assertRedirects(response, reverse("sales:detail", args=[self.quote.pk]))
        project = Project.objects.get(owner=self.owner)
        item = self.version.items.get()
        self.assertFalse(item.snapshot["complete"])
        self.assertEqual(item.total, Decimal("80"))
        self.assertTrue(project.current_revision.quick_entry)
        with self.assertRaises(ValidationError):
            publish(owner=self.owner, version_id=self.version.pk)
        publish(owner=self.owner, version_id=self.version.pk, confirm_limitations=True)
        response = self.client.get(
            reverse("sales:piece_suggestion", args=[project.pk]), {"quantity": 3}
        )
        self.assertEqual(response.json()["manual_price"], "120.00")
        self.assertFalse(response.json()["complete"])

    def test_calculation_and_description_are_owned_and_quantity_aware(self):
        project = create_project(
            owner=self.owner,
            name="Ficha",
            description="Descrição pronta",
            estimated_seconds=3600,
            hourly_rate=Decimal("50"),
            percentage=Decimal(0),
        )
        url = reverse("sales:piece_suggestion", args=[project.pk])
        self.assertEqual(
            self.client.get(url, {"quantity": 2}).json()["calculated_price"], "100.00"
        )
        self.assertEqual(self.client.get(url).json()["description"], "Descrição pronta")
        self.assertEqual(self.client.get(url, {"quantity": 0}).status_code, 400)
        other = get_user_model().objects.create_user(username="foreign_inline")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_duplicate_or_published_creates_no_orphan_piece(self):
        for data in (
            {
                "new_piece_name": "Sem preço",
                "quantity": 1,
                "discount": 0,
                "fixed_discount": 0,
            },
            {
                "new_piece_name": "Inválida",
                "quantity": 0,
                "manual_price": 20,
                "discount": 0,
                "fixed_discount": 0,
            },
        ):
            self.assertEqual(self.client.post(self.path, data).status_code, 200)
        self.assertFalse(Project.objects.filter(owner=self.owner).exists())
        add_quote_item(
            owner=self.owner,
            version_id=self.version.pk,
            new_piece_name="Existente",
            quantity=1,
            manual_price=Decimal("20"),
        )
        count = Project.objects.filter(owner=self.owner).count()
        with self.assertRaises(ValidationError):
            add_quote_item(
                owner=self.owner,
                version_id=self.version.pk,
                new_piece_name="Existente",
                quantity=1,
                manual_price=Decimal("20"),
            )
        publish(owner=self.owner, version_id=self.version.pk, confirm_limitations=True)
        with self.assertRaises(ValidationError):
            add_quote_item(
                owner=self.owner,
                version_id=self.version.pk,
                new_piece_name="Outra",
                quantity=1,
                manual_price=Decimal("20"),
            )
        self.assertEqual(Project.objects.filter(owner=self.owner).count(), count)
        self.assertEqual(QuoteItem.objects.filter(version=self.version).count(), 1)
