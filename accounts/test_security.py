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
