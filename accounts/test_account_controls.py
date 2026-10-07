import uuid
from django.contrib.auth import get_user_model
from django.http import Http404
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from production import tests as production_fixtures
from sales.models import ShareToken
from sales.services import make_token, get_token
from .security import account_action


class AccountControlTests(TestCase):
    def setUp(self):
        production_fixtures.ProductionTests.setUp(self)
        self.version.refresh_from_db()

    def test_password_confirmed_revocation_is_idempotent_and_does_not_touch_other_accounts(
        self,
    ):
        password = "Synthetic-Account-Security-91!"
        self.owner.set_password(password)
        self.owner.save()
        raw = make_token(self.version)
        with self.assertRaises(ValidationError):
            account_action(
                owner=self.owner,
                password="wrong",
                key=uuid.uuid4(),
                reason="Teste",
                action="revoke",
            )
        self.assertIsNotNone(get_token(raw))
        kwargs = dict(
            owner=self.owner,
            password=password,
            key=uuid.uuid4(),
            reason="Link vazou",
            action="revoke",
        )
        result = account_action(**kwargs)
        self.assertEqual(account_action(**kwargs), result)
        self.assertGreater(result["revoked"], 0)
        with self.assertRaises(Http404):
            get_token(raw)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_suspension_invalidates_login_and_portal_without_deleting_history(self):
        from .demo import create_demo

        password = "Synthetic-Account-Security-92!"
        self.owner.set_password(password)
        self.owner.save()
        workspace = create_demo(self.owner)
        raw = make_token(self.version)
        account_action(
            owner=self.owner,
            password=password,
            key=uuid.uuid4(),
            reason="Pausa voluntária",
            action="suspend",
        )
        self.owner.refresh_from_db()
        workspace.demo_user.refresh_from_db()
        self.assertFalse(self.owner.is_active)
        self.assertFalse(workspace.demo_user.is_active)
        self.assertFalse(
            self.client.login(username=self.owner.username, password=password)
        )
        with self.assertRaises(Http404):
            get_token(raw)
        self.assertEqual(self.owner.material_set.count(), 1)
        self.assertTrue(self.quote.versions.filter(pk=self.version.pk).exists())

    def test_password_change_preserves_current_session_and_invalidates_other_session(
        self,
    ):
        old = "Synthetic-Account-Security-93!"
        new = "Synthetic-Account-Security-94!"
        self.owner.set_password(old)
        self.owner.save()
        other = Client()
        self.client.login(username=self.owner.username, password=old)
        other.login(username=self.owner.username, password=old)
        response = self.client.post(
            reverse("password_change"),
            {"old_password": old, "new_password1": new, "new_password2": new},
        )
        self.assertRedirects(response, reverse("password_change_done"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(other.get(reverse("dashboard")).status_code, 302)

    def test_disabled_owner_portal_is_denied_even_without_explicit_token_revocation(
        self,
    ):
        raw = make_token(self.version)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(Http404):
            get_token(raw)
