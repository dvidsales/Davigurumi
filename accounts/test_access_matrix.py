"""Cross-account route matrix: reads and writes must reject valid foreign IDs."""

import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from production import tests as production_fixtures


class AccessMatrixTests(TestCase):
    setUp = production_fixtures.ProductionTests.setUp

    def test_private_identifiers_are_not_accessible_from_another_account(self):
        from production.services import reserve_order, start_session, stop_session
        from materials.models import StockReservation
        from purchasing.models import Purchase
        from purchasing.services import add_item
        from finance.services import record_payment
        from finance.models import PaymentAllocation, Receivable
        from operations.models import Notification
        from portability.models import ImportJob

        reserve_order(owner=self.owner, order_id=self.order.pk, key=uuid.uuid4())
        reservation = StockReservation.objects.get(reference=self.item.pk)
        session = start_session(owner=self.owner, item_id=self.item.pk)
        stop_session(owner=self.owner, session_id=session.pk)
        project = self.version.items.get().project_revision.project
        line = project.current_revision.materials.get()
        purchase = Purchase.objects.create(owner=self.owner, date=timezone.localdate())
        purchase_item = add_item(
            owner=self.owner,
            purchase_id=purchase.pk,
            material_id=self.material.pk,
            quantity=Decimal("5"),
            unit_price=Decimal("1"),
        )
        record_payment(
            owner=self.owner,
            version_id=self.version.pk,
            amount=Decimal("1"),
            date=timezone.localdate(),
            method="pix",
            key=uuid.uuid4(),
        )
        allocation = PaymentAllocation.objects.get()
        receivable = Receivable.objects.create(
            order=self.order, amount=Decimal("1"), due_date=timezone.localdate()
        )
        notification = Notification.objects.create(
            owner=self.owner, key="matrix", message="Privado"
        )
        job = ImportJob.objects.create(
            owner=self.owner, rows=[], errors=[]
        )
        reader = get_user_model().objects.create_user(
            username="matrix_intruder", email="matrix_intruder@example.test"
        )
        self.client.force_login(reader)
        routes = {
            "materials:detail": self.material.pk,
            "materials:edit": self.material.pk,
            "materials:stock_action": self.material.pk,
            "materials:conversion": self.material.pk,
            "materials:archive": self.material.pk,
            "materials:reservation_action": reservation.pk,
            "projects:detail": project.pk,
            "projects:edit": project.pk,
            "projects:material": project.pk,
            "projects:alternative": line.pk,
            "projects:edit_line": line.pk,
            "purchasing:detail": purchase.pk,
            "purchasing:edit": purchase.pk,
            "purchasing:item": purchase.pk,
            "purchasing:allocation": purchase.pk,
            "purchasing:edit_item": purchase_item.pk,
            "purchasing:receive": purchase_item.pk,
            "purchasing:action": purchase.pk,
            "sales:detail": self.quote.pk,
            "sales:compare": self.quote.pk,
            "sales:new_version": self.quote.pk,
            "sales:publish": self.version.pk,
            "sales:item": self.version.pk,
            "sales:edit_version": self.version.pk,
            "sales:reissue": self.version.pk,
            "sales:revoke": self.version.pk,
            "sales:owner_pdf": self.version.pk,
            "sales:image_upload": self.version.pk,
            "sales:edit_item": self.version.items.get().pk,
            "sales:remove_item": self.version.items.get().pk,
            "production:detail": self.order.pk,
            "production:settings": self.order.pk,
            "production:expense": self.order.pk,
            "production:action": self.order.pk,
            "production:start": self.item.pk,
            "production:convert": self.version.pk,
            "production:correction": session.pk,
            "production:stop": session.pk,
            "finance:payment": self.version.pk,
            "finance:refund": allocation.pk,
            "finance:receivable": self.order.pk,
            "finance:cancel_receivable": receivable.pk,
            "operations:read": notification.pk,
            "portability:preview": job.pk,
            "portability:confirm": job.pk,
        }
        for name, identifier in routes.items():
            url = reverse(name, args=[identifier])
            with self.subTest(route=name):
                self.assertIn(self.client.get(url).status_code, [404, 405])
                self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.material.refresh_from_db()
        self.order.refresh_from_db()
        self.assertFalse(self.material.is_archived)
        self.assertEqual(self.order.status, "paused")
        self.assertEqual(self.material.physical_stock, Decimal("508"))
