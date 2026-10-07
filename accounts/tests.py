from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()
PASSWORD = "Synthetic-test-password-7!"

class AccountTests(TestCase):
    def test_signup_login_and_post_logout(self):
        response = self.client.post(reverse("signup"), {"first_name": "Ana", "username": "ana",
            "email": "ANA@example.test", "password1": PASSWORD, "password2": PASSWORD})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(User.objects.get(username="ana").email, "ana@example.test")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertRedirects(self.client.post(reverse("login"), {"username": "ana", "password": PASSWORD}), reverse("dashboard"))

    def test_email_is_unique_ignoring_case_at_database_level(self):
        User.objects.create_user(username="ana", email="ana@example.test", password=PASSWORD)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="outra", email="ANA@example.test", password=PASSWORD)

    def test_duplicate_email_form_is_rejected(self):
        User.objects.create_user(username="ana", email="ana@example.test", password=PASSWORD)
        response = self.client.post(reverse("signup"), {"username": "outra", "email": "ANA@example.test",
            "password1": PASSWORD, "password2": PASSWORD})
        self.assertContains(response, "Este e-mail já possui uma conta")
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_rejected(self):
        self.client.post(reverse("signup"), {"username": "ana", "email": "ana@example.test", "password1": "123", "password2": "123"})
        self.assertFalse(User.objects.exists())

    def test_csrf_is_required_for_signup(self):
        response = Client(enforce_csrf_checks=True).post(reverse("signup"), {"username": "ana"})
        self.assertEqual(response.status_code, 403)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_recovery_changes_password_and_token_cannot_be_reused(self):
        user = User.objects.create_user(username="ana", email="ana@example.test", password=PASSWORD)
        self.assertRedirects(self.client.post(reverse("password_reset"), {"email": user.email}), reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = next(line.strip() for line in mail.outbox[0].body.splitlines() if line.startswith("http"))
        response = self.client.get(link)
        reset_url = response.url
        self.assertContains(self.client.get(reset_url), "Definir nova senha")
        self.assertRedirects(self.client.post(reset_url, {"new_password1": "Another-Synthetic-password-8!",
            "new_password2": "Another-Synthetic-password-8!"}), reverse("password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("Another-Synthetic-password-8!"))
        self.assertContains(self.client.get(link, follow=True), "Este link expirou")

    def test_private_dashboard_has_no_store_header(self):
        user = User.objects.create_user(username="ana", email="ana@example.test", password=PASSWORD)
        self.client.force_login(user)
        self.assertIn("no-store", self.client.get(reverse("dashboard"))["Cache-Control"])
