import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from projects.services import create_project
from production.services import create_order, apply_amendment
from finance.services import record_payment
from django.utils import timezone
from .services import (
    create_quote,
    add_quote_item,
    publish,
    decide,
    new_version,
    edit_draft_item,
)


class AmendmentTests(TestCase):
    def test_new_accept_changes_current_price_and_preserves_prior_price_and_cash(self):
        owner = get_user_model().objects.create_user(
            username="amend", email="amend@example.test"
        )
        project = create_project(
            owner=owner,
            name="Peça",
            estimated_seconds=3600,
            hourly_rate=Decimal("100"),
            percentage=Decimal(0),
        )
        quote = create_quote(owner=owner)
        old = quote.versions.get()
        add_quote_item(
            owner=owner, version_id=old.pk, project_id=project.pk, quantity=1
        )
        old, raw = publish(owner=owner, version_id=old.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        order = create_order(owner=owner, version_id=old.pk)
        record_payment(
            owner=owner,
            version_id=old.pk,
            amount=Decimal("50"),
            date=timezone.localdate(),
            method="pix",
            key=uuid.uuid4(),
        )
        new = new_version(owner=owner, quote_id=quote.pk)
        edit_draft_item(
            owner=owner,
            item_id=new.items.get().pk,
            project_id=project.pk,
            quantity=1,
            manual_price=Decimal("120"),
        )
        new, raw = publish(owner=owner, version_id=new.pk)
        decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
        apply_amendment(owner=owner, order_id=order.pk, version_id=new.pk)
        order.refresh_from_db()
        old.refresh_from_db()
        self.assertEqual(old.total, Decimal("100"))
        self.assertEqual(old.status, "approved")
        self.assertEqual(order.total, Decimal("120"))
        self.assertEqual(order.net_received, Decimal("50"))
        self.assertEqual(order.balance, Decimal("70"))
