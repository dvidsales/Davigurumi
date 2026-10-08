from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .services import create_quote, add_quote_item, publish


class WorkflowNavigationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="steps", email="steps@example.test"
        )
        self.client.force_login(self.owner)
        self.quote = create_quote(owner=self.owner)
        self.version = self.quote.versions.get()

    def test_all_steps_accessible_on_empty_draft_without_mutations(self):
        for step in range(1, 5):
            response = self.client.get(
                reverse("sales:workflow", args=[self.version.pk, step]), follow=True
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'aria-current="step"', count=1)
            for other_step in range(1, 5):
                self.assertContains(
                    response,
                    reverse("sales:workflow", args=[self.version.pk, other_step]),
                )
        self.version.refresh_from_db()
        self.assertIsNone(self.version.published_at)
        self.assertFalse(self.version.items.exists())

    def test_conditions_save_and_published_steps_are_read_only(self):
        response = self.client.post(
            reverse("sales:edit_version", args=[self.version.pk]),
            {"terms": "Condições editadas", "valid_days": 20},
        )
        self.assertEqual(response.status_code, 302)
        self.version.refresh_from_db()
        self.assertEqual(self.version.terms, "Condições editadas")
        add_quote_item(
            owner=self.owner,
            version_id=self.version.pk,
            new_piece_name="Peça",
            quantity=1,
            manual_price=Decimal("20"),
        )
        publish(owner=self.owner, version_id=self.version.pk, confirm_limitations=True)
        self.version.refresh_from_db()
        content_hash = self.version.content_hash
        for step in range(1, 5):
            self.assertEqual(
                self.client.get(
                    reverse("sales:workflow", args=[self.version.pk, step]), follow=True
                ).status_code,
                200,
            )
        self.version.refresh_from_db()
        self.assertEqual(self.version.content_hash, content_hash)
        self.assertEqual(
            self.client.get(
                reverse("sales:workflow", args=[self.version.pk, 5])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("sales:workflow", args=[self.version.pk, 4])
            ).status_code,
            405,
        )

    def test_other_account_cannot_navigate_quote_steps(self):
        other = get_user_model().objects.create_user(username="foreign_steps")
        self.client.force_login(other)
        for step in range(1, 5):
            self.assertEqual(
                self.client.get(
                    reverse("sales:workflow", args=[self.version.pk, step])
                ).status_code,
                404,
            )
