"""Regression checks for bounded queries as account history grows."""

from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from production import tests as fixtures
from operations.reporting import overview
from projects.services import create_project, add_material
from sales.services import create_quote, add_quote_item, publish, decide
from production.services import create_order
from decimal import Decimal
import uuid


class ResourceTests(TestCase):
    setUp = fixtures.ProductionTests.setUp

    def test_dashboard_queries_do_not_grow_per_order(self):
        with CaptureQueriesContext(connection) as captured:
            overview(self.owner)
        baseline = len(captured)
        for _ in range(8):
            quote = create_quote(owner=self.owner)
            version_id = quote.versions.get().pk
            add_quote_item(
                owner=self.owner,
                version_id=version_id,
                project_id=self.item.source_item.project_revision.project_id,
                quantity=1,
            )
            _, raw = publish(owner=self.owner, version_id=version_id)
            decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
            create_order(owner=self.owner, version_id=version_id)
        with CaptureQueriesContext(connection) as captured:
            overview(self.owner)
        self.assertLessEqual(
            len(captured), baseline + 2, [entry["sql"] for entry in captured]
        )
