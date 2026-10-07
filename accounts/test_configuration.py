"""WSGI must fail closed without production configuration; no server is started."""

import os
import secrets
import subprocess
import sys
from django.conf import settings
from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def run_wsgi(self, **values):
        env = os.environ.copy()
        for key in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS"):
            env.pop(key, None)
        env.update(values)
        return subprocess.run(
            [sys.executable, "-c", "import config.wsgi"],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_wsgi_refuses_missing_production_configuration(self):
        result = self.run_wsgi()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_wsgi_rejects_development_key_and_wildcard_hosts(self):
        result = self.run_wsgi(
            DJANGO_SECRET_KEY="development-only-" + "x" * 60,
            DJANGO_ALLOWED_HOSTS="review.invalid",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("chave de produção", result.stderr)
        result = self.run_wsgi(
            DJANGO_SECRET_KEY=secrets.token_urlsafe(64), DJANGO_ALLOWED_HOSTS="*"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hosts explícitos", result.stderr)

    def test_wsgi_accepts_explicit_synthetic_configuration(self):
        result = self.run_wsgi(
            DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
            DJANGO_ALLOWED_HOSTS="review.invalid",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
