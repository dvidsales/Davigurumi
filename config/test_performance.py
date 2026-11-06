from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from config import pwa
from config.performance import _metrics, timed_operation


class PerformanceTests(TestCase):
    @override_settings(PERFORMANCE_LOGGING=True)
    def test_logs_contain_aggregate_metrics_not_path_query_or_parameters(self):
        with self.assertLogs("davigurumi.performance", level="INFO") as logs:
            response = self.client.get(
                reverse("login"), {"private_marker": "must-never-be-logged"}
            )
        self.assertEqual(response.status_code, 200)
        message = " ".join(logs.output)
        self.assertIn("route=login", message)
        self.assertIn("db_count=", message)
        self.assertNotIn("must-never-be-logged", message)
        self.assertNotIn("SELECT", message)
        self.assertIsNone(_metrics.get())

    def test_remote_failure_is_timed_and_propagates(self):
        @timed_operation("remote")
        def unavailable():
            raise OSError("synthetic unavailable")

        counters = {"remote_count": 0, "remote_ms": 0}
        token = _metrics.set(counters)
        try:
            with self.assertRaises(OSError):
                unavailable()
            self.assertEqual(counters["remote_count"], 1)
            self.assertGreaterEqual(counters["remote_ms"], 0)
        finally:
            _metrics.reset(token)

    def test_version_exposes_only_valid_commit_prefix(self):
        with patch.dict("os.environ", {"RENDER_GIT_COMMIT": "a" * 40}):
            self.assertEqual(
                self.client.get(reverse("version")).json(), {"release": "a" * 12}
            )
        with patch.dict("os.environ", {"RENDER_GIT_COMMIT": "invalid/configuration"}):
            self.assertEqual(
                self.client.get(reverse("version")).json(), {"release": "unknown"}
            )

    def test_service_worker_uses_hashed_assets_and_changes_namespace(self):
        with patch.object(
            pwa, "static", side_effect=lambda name: "/static/" + name + ".hash-one"
        ):
            first = self.client.get(reverse("service_worker")).content.decode()
        with patch.object(
            pwa, "static", side_effect=lambda name: "/static/" + name + ".hash-two"
        ):
            second = self.client.get(reverse("service_worker")).content.decode()
        first_cache = next(
            line for line in first.splitlines() if line.startswith("const PUBLIC_CACHE")
        )
        second_cache = next(
            line
            for line in second.splitlines()
            if line.startswith("const PUBLIC_CACHE")
        )
        self.assertNotEqual(first_cache, second_cache)
        self.assertIn("app.css.hash-one", first)
        self.assertIn('event.request.method !== "GET"', first)
        self.assertIn("!ASSETS.includes(url.pathname)", first)
