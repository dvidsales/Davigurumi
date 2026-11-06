"""Synthetic visual-review fixture; refuses non-local or unmarked databases.
Run once on an empty, disposable review database. Never use on the beta.
"""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_DEBUG", "1")
import django

django.setup()
from django.db import connection

if (
    os.getenv("DAVIGURUMI_SMOKE_ISOLATED") != "1"
    or not connection.settings_dict["NAME"].startswith("davigurumi_audit_ui_")
    or connection.settings_dict["HOST"] not in ("localhost", "127.0.0.1", "::1")
):
    raise RuntimeError(
        "Use somente banco local descartável davigurumi_audit_ui_ com DAVIGURUMI_SMOKE_ISOLATED=1."
    )
from production.test_read_queries import ReadFixture
from production.models import Order, ProductionSession
from django.utils import timezone
from decimal import Decimal

ReadFixture.setUpTestData()
owner = ReadFixture.owner
owner.set_password("Synthetic-Audit-Only-2026!")
owner.save(update_fields=["password"])
for _ in range(26):
    ReadFixture.make_order(1)
now = timezone.now()
Order.objects.filter(pk=ReadFixture.order.pk).update(
    planned_start=now.date(), production_due=now.date()
)
for _ in range(50):
    ProductionSession.objects.create(
        owner=owner,
        item=ReadFixture.item,
        started_at=now,
        ended_at=now,
        seconds=120,
        hourly_rate=Decimal(30),
    )
