from django.test import TestCase, override_settings
from django.urls import reverse


class SecurityTests(TestCase):
    @override_settings(AUTH_RATE_LIMIT=2)
    def test_login_limit_is_shared_between_sessions_and_does_not_log_identifiers(self):
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    reverse("login"), {"username": "unknown", "password": "wrong"}
                ).status_code,
                200,
            )
        self.assertEqual(
            self.client.post(
                reverse("login"), {"username": "another", "password": "wrong"}
            ).status_code,
            429,
        )
        from .models import AuthThrottle

        key = AuthThrottle.objects.get().key
        self.assertNotIn("unknown", key)
        self.assertNotIn("127.0.0.1", key)

    def test_security_headers(self):
        response = self.client.get(reverse("login"))
        self.assertIn("object-src 'none'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_oversized_request_is_rejected_before_csrf_or_form_processing(self):
        from django.test import Client

        response = Client(enforce_csrf_checks=True).post(
            reverse("signup"), {}, CONTENT_LENGTH=str(7 * 1024 * 1024)
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("object-src 'none'", response["Content-Security-Policy"])
        self.assertIn("no-store", response["Cache-Control"])

    @override_settings(PRIVATE_UPLOAD_LIMIT=64)
    def test_multipart_chunks_are_limited_without_trusting_upload_size(self):
        from django.contrib.auth import get_user_model
        from django.core.files.uploadedfile import SimpleUploadedFile

        user = get_user_model().objects.create_user(
            username="upload_budget", email="upload_budget@example.test"
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("portability:index"),
            {"upload": SimpleUploadedFile("table.csv", b"x" * 256)},
        )
        self.assertEqual(response.status_code, 400)
        from portability.models import ImportJob

        self.assertFalse(ImportJob.objects.exists())

    @override_settings(AUTH_RATE_LIMIT=1)
    def test_demo_password_and_reset_endpoints_are_throttled(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="password_budget", email="password_budget@example.test"
        )
        self.client.force_login(user)
        for path in ["/demo/", "/conta/redefinir/invalid/invalid/"]:
            self.client.post(path, {})
            blocked = self.client.post(path, {})
            self.assertEqual(blocked.status_code, 429, path)
            self.assertIn("no-store", blocked["Cache-Control"])
            self.assertIn("Retry-After", blocked)

    @override_settings(PORTAL_READ_RATE_LIMIT=1)
    def test_public_read_limit_is_shared_across_tokens_and_sessions(self):
        self.assertEqual(self.client.get("/portal/invalid/").status_code, 404)
        from django.test import Client

        blocked = Client().get("/portal/another-invalid/")
        self.assertEqual(blocked.status_code, 429)

    def test_reset_and_portal_tokens_are_redacted_from_log_records(self):
        import logging
        from config.logging import RedactPortalToken

        record = logging.LogRecord(
            "django.server",
            logging.INFO,
            "",
            0,
            "GET %s %s",
            ("/portal/secret-value/pdf/", "/conta/redefinir/user-id/reset-secret/"),
            None,
        )
        RedactPortalToken().filter(record)
        self.assertNotIn("secret-value", record.getMessage())
        self.assertNotIn("reset-secret", record.getMessage())
        self.assertNotIn("user-id", record.getMessage())
        self.assertIn("[redacted]", record.getMessage())

    def test_csrf_failure_still_has_security_and_private_cache_headers(self):
        from django.test import Client

        response = Client(enforce_csrf_checks=True).post(reverse("signup"), {})
        self.assertEqual(response.status_code, 403)
        self.assertIn("object-src 'none'", response["Content-Security-Policy"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            response["Permissions-Policy"], "camera=(), microphone=(), geolocation=()"
        )

    def test_transient_cleanup_is_a_dry_run_by_default_and_preserves_history(self):
        from django.core.management import call_command
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        from io import StringIO
        from .models import AuthThrottle
        from materials.models import Material
        from portability.models import ImportJob

        owner = get_user_model().objects.create_user(
            username="cleanup", email="cleanup@example.test"
        )
        material = Material.objects.create(
            owner=owner, name="Histórico", kind="yarn", unit="g"
        )
        row = AuthThrottle.objects.create(
            key="x" * 64, expires_at=timezone.now() - timedelta(days=2)
        )
        preview = ImportJob.objects.create(owner=owner)
        ImportJob.objects.filter(pk=preview.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        call_command("prune_transient", stdout=StringIO())
        self.assertTrue(AuthThrottle.objects.filter(pk=row.pk).exists())
        self.assertTrue(ImportJob.objects.filter(pk=preview.pk).exists())
        call_command("prune_transient", apply=True, stdout=StringIO())
        self.assertFalse(AuthThrottle.objects.filter(pk=row.pk).exists())
        self.assertFalse(ImportJob.objects.filter(pk=preview.pk).exists())
        self.assertTrue(Material.objects.filter(pk=material.pk).exists())

    def test_login_does_not_redirect_to_an_external_next_url(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="redirect_guard",
            email="redirect_guard@example.test",
            password="Synthetic-Redirect-Password-96!",
        )
        response = self.client.post(
            reverse("login"),
            {
                "username": user.username,
                "password": "Synthetic-Redirect-Password-96!",
                "next": "https://attacker.invalid/collect",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    @override_settings(WRITE_RATE_LIMIT=1)
    def test_write_rate_is_shared_across_non_auth_routes(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="write_budget", email="write_budget@example.test"
        )
        self.client.force_login(user)
        self.assertEqual(
            self.client.post(reverse("sales:clients"), {}).status_code, 200
        )
        response = self.client.post(reverse("purchasing:suppliers"), {})
        self.assertEqual(response.status_code, 429)
        self.assertIn("no-store", response["Cache-Control"])

    @override_settings(PUBLIC_SIGNUP_ENABLED=False)
    def test_closed_signup_rejects_reads_and_posts_without_creating_accounts(self):
        from django.contrib.auth import get_user_model

        self.assertEqual(self.client.get(reverse("signup")).status_code, 403)
        response = self.client.post(
            reverse("signup"),
            {
                "username": "intruder",
                "email": "intruder@example.test",
                "password1": "Synthetic-Closed-Signup-98!",
                "password2": "Synthetic-Closed-Signup-98!",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.exists())
        self.assertIn("no-store", response["Cache-Control"])

    @override_settings(REPORT_READ_RATE_LIMIT=1)
    def test_expensive_read_limit_is_shared_across_dashboard_and_reports(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="read_budget", email="read_budget@example.test"
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        response = self.client.get(reverse("operations:reports"))
        self.assertEqual(response.status_code, 429)
        self.assertIn("no-store", response["Cache-Control"])
