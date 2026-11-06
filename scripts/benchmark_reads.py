#!/usr/bin/env python
"""Read-only request benchmark on synthetic fixtures in a fresh Django TEST database.
Never targets the published beta. Times are local test-client timings, not production.
"""
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_DEBUG", "1")
import django

django.setup()
from django.db import connection
from django.test import TestCase
from django.test.runner import DiscoverRunner
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from production.models import ProductionSession, Order
from production.costs import cost_summary
from production.test_read_queries import ReadFixture
from decimal import Decimal

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", required=True)
parser.add_argument("--samples", type=int, default=30)
args = parser.parse_args()
if args.samples < 30:
    parser.error("Use pelo menos 30 amostras aquecidas.")
results = {
    "method": "local Django test client; warm; SQL measured; no browser/network/cold-start",
    "samples": args.samples,
    "database": connection.vendor,
    "routes": {},
}


class ReadBenchmark(ReadFixture, TestCase):
    def test_benchmark(self):
        now = timezone.now()
        Order.objects.filter(pk=self.order.pk).update(
            planned_start=now.date(), production_due=now.date()
        )
        for _ in range(50):
            ProductionSession.objects.create(
                owner=self.owner,
                item=self.item,
                started_at=now,
                ended_at=now,
                seconds=120,
                hourly_rate=Decimal(30),
            )
        with CaptureQueriesContext(connection) as queries:
            cost_summary(self.order)
        results["cost_summary_50_sessions_queries"] = len(queries)
        if connection.vendor == "postgresql" and hasattr(
            ProductionSession.objects, "with_effective_seconds"
        ):
            from materials.selectors import stock_levels

            results["query_plans"] = {
                "sessions": ProductionSession.objects.with_effective_seconds()
                .filter(item=self.item)
                .explain(),
                "stock": stock_levels(self.owner).explain(),
            }
        self.client.force_login(self.owner)
        for route_number, route in enumerate(
            (
                "/",
                "/materiais/",
                "/orcamentos/",
                "/pedidos/",
                "/pedidos/calendario/",
                "/notificacoes/relatorios/",
            )
        ):
            # Separate synthetic loopback clients per route; do not weaken rate limits.
            self.client.defaults["REMOTE_ADDR"] = "127.0.1." + str(route_number + 1)
            self.assertEqual(self.client.get(route).status_code, 200)
            samples, counts, volumes = [], [], []
            for _ in range(args.samples):
                start = perf_counter()
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                samples.append((perf_counter() - start) * 1000)
                counts.append(len(queries))
                volumes.append(len(response.content))
            results["routes"][route] = {
                "median_ms": round(statistics.median(samples), 2),
                "p95_ms": round(sorted(samples)[math.ceil(0.95 * len(samples)) - 1], 2),
                "queries_min": min(counts),
                "queries_max": max(counts),
                "response_bytes_max": max(volumes),
            }


runner = DiscoverRunner(verbosity=0, interactive=False)
runner.setup_test_environment()
old_config = None
try:
    old_config = runner.setup_databases()
    result = runner.run_suite(unittest.TestSuite([ReadBenchmark("test_benchmark")]))
    if not result.wasSuccessful():
        sys.exit(1)
    Path(args.output).write_text(json.dumps(results, indent=2))
finally:
    if old_config is not None:
        runner.teardown_databases(old_config)
    runner.teardown_test_environment()
