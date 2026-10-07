from datetime import date
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from materials.models import Material, StockMovement
from materials.stock import add_conversion
from .models import Purchase, Receipt, Supplier
from .services import (
    add_item,
    confirm_purchase,
    receive_purchase,
    cancel_purchase,
    repeat_purchase,
    distribute,
)

D = Decimal


class PurchaseTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="buyer", email="buyer@example.test"
        )
        self.other = get_user_model().objects.create_user(
            username="other", email="other@example.test"
        )
        self.material = Material.objects.create(
            owner=self.owner, name="Fio", kind="yarn", unit="g"
        )
        self.purchase = Purchase.objects.create(
            owner=self.owner, date=timezone.localdate(), freight=D("10")
        )
        self.item = add_item(
            owner=self.owner,
            purchase_id=self.purchase.pk,
            material_id=self.material.pk,
            quantity=D("100"),
            unit_price=D(".1"),
        )

    def test_confirm_does_not_receive_and_partial_cancellation_keeps_received_stock(
        self,
    ):
        confirm_purchase(owner=self.owner, purchase_id=self.purchase.pk)
        self.assertEqual(self.material.physical_stock, 0)
        result = receive_purchase(
            owner=self.owner,
            purchase_id=self.purchase.pk,
            quantities={self.item.pk: D("40")},
            key=uuid.uuid4(),
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(self.material.physical_stock, D("40"))
        self.assertEqual(self.material.layers.get().unit_cost, D(".2"))
        cancel_purchase(owner=self.owner, purchase_id=self.purchase.pk)
        self.assertEqual(self.material.physical_stock, D("40"))
        with self.assertRaises(ValidationError):
            receive_purchase(
                owner=self.owner,
                purchase_id=self.purchase.pk,
                quantities={self.item.pk: D("60")},
                key=uuid.uuid4(),
            )

    def test_receipt_is_idempotent(self):
        confirm_purchase(owner=self.owner, purchase_id=self.purchase.pk)
        key = uuid.uuid4()
        kwargs = dict(
            owner=self.owner,
            purchase_id=self.purchase.pk,
            quantities={self.item.pk: D("100")},
            key=key,
        )
        first = receive_purchase(**kwargs)
        self.assertEqual(receive_purchase(**kwargs), first)
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_receipt_over_order_rolls_back_all_state(self):
        confirm_purchase(owner=self.owner, purchase_id=self.purchase.pk)
        with self.assertRaises(ValidationError):
            receive_purchase(
                owner=self.owner,
                purchase_id=self.purchase.pk,
                quantities={self.item.pk: D("101")},
                key=uuid.uuid4(),
            )
        self.assertFalse(Receipt.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_repeated_purchase_is_draft_with_no_receipt_and_no_mutation(self):
        confirm_purchase(owner=self.owner, purchase_id=self.purchase.pk)
        new = repeat_purchase(
            owner=self.owner, purchase_id=self.purchase.pk, date=timezone.localdate()
        )
        self.assertNotEqual(new.pk, self.purchase.pk)
        self.assertEqual(new.status, "draft")
        self.assertEqual(new.items.get().received, 0)
        self.assertEqual(self.material.physical_stock, 0)

    def test_changed_conversion_does_not_change_confirmed_receipt(self):
        add_conversion(
            owner=self.owner,
            material_id=self.material.pk,
            name="novelo",
            factor=D("254"),
        )
        other = Purchase.objects.create(owner=self.owner, date=timezone.localdate())
        item = add_item(
            owner=self.owner,
            purchase_id=other.pk,
            material_id=self.material.pk,
            quantity=D("3"),
            unit_price=D("25.40"),
            unit="novelo",
        )
        confirm_purchase(owner=self.owner, purchase_id=other.pk)
        add_conversion(
            owner=self.owner,
            material_id=self.material.pk,
            name="novelo",
            factor=D("200"),
        )
        receive_purchase(
            owner=self.owner,
            purchase_id=other.pk,
            quantities={item.pk: D("762")},
            key=uuid.uuid4(),
        )
        self.assertEqual(self.material.physical_stock, D("762"))
        self.assertEqual(
            StockMovement.objects.get().conversion_snapshot["factor"], "254.000000"
        )

    def test_foreign_material_and_purchase_are_denied(self):
        with self.assertRaises(Http404):
            add_item(
                owner=self.other,
                purchase_id=self.purchase.pk,
                material_id=self.material.pk,
                quantity=D("1"),
                unit_price=D("1"),
            )
        foreign = Material.objects.create(
            owner=self.other, name="Privado", kind="yarn", unit="g"
        )
        with self.assertRaises(Http404):
            add_item(
                owner=self.owner,
                purchase_id=self.purchase.pk,
                material_id=foreign.pk,
                quantity=D("1"),
                unit_price=D("1"),
            )

    def test_cent_distribution_is_exact_and_nonnegative(self):
        shares = distribute(D(".02"), [D("1"), D("1"), D("1")])
        self.assertEqual(shares, [D(".01"), D(".01"), D("0")])
        self.assertEqual(sum(shares), D(".02"))
        with self.assertRaises(ValidationError):
            distribute(D("1"), [D("0")])


class DraftEditingTests(TestCase):
    def test_repeated_purchase_can_change_items_without_touching_original(self):
        from .services import edit_item, repeat_purchase

        owner = get_user_model().objects.create_user(
            username="buyer_editor", email="buyer_editor@example.test"
        )
        material = Material.objects.create(
            owner=owner, name="Fio", kind="yarn", unit="g"
        )
        purchase = Purchase.objects.create(owner=owner, date=date(2026, 10, 7))
        original = add_item(
            owner=owner,
            purchase_id=purchase.pk,
            material_id=material.pk,
            quantity=D("100"),
            unit_price=D(".1"),
        )
        new = repeat_purchase(
            owner=owner, purchase_id=purchase.pk, date=date(2026, 10, 8)
        )
        edit_item(
            owner=owner,
            item_id=new.items.get().pk,
            material_id=material.pk,
            quantity=D("200"),
            unit_price=D(".2"),
        )
        original.refresh_from_db()
        self.assertEqual(original.quantity, D("100"))
        self.assertEqual(new.items.get().quantity, D("200"))
        self.assertEqual(material.physical_stock, 0)
        confirm_purchase(owner=owner, purchase_id=new.pk)
        with self.assertRaises(ValidationError):
            edit_item(
                owner=owner,
                item_id=new.items.get().pk,
                material_id=material.pk,
                quantity=D("1"),
                unit_price=D(".1"),
            )


class ManualAllocationTests(TestCase):
    setUp = PurchaseTests.setUp

    def test_manual_costs_freeze_and_receipts_use_each_cost(self):
        second = add_item(
            owner=self.owner,
            purchase_id=self.purchase.pk,
            material_id=self.material.pk,
            quantity=D("50"),
            unit_price=D(".2"),
        )
        costs = {self.item.pk: D("12"), second.pk: D("18")}
        confirm_purchase(
            owner=self.owner, purchase_id=self.purchase.pk, manual_allocations=costs
        )
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.allocation_mode, "manual")
        self.assertEqual(self.material.physical_stock, 0)
        confirm_purchase(
            owner=self.owner, purchase_id=self.purchase.pk, manual_allocations=costs
        )
        with self.assertRaises(ValidationError):
            confirm_purchase(
                owner=self.owner,
                purchase_id=self.purchase.pk,
                manual_allocations={self.item.pk: D("13"), second.pk: D("17")},
            )
        receive_purchase(
            owner=self.owner,
            purchase_id=self.purchase.pk,
            quantities={self.item.pk: D("100"), second.pk: D("50")},
            key=uuid.uuid4(),
        )
        self.assertEqual(
            set(self.material.layers.values_list("unit_cost", flat=True)),
            {D(".12"), D(".36")},
        )

    def test_invalid_or_foreign_costs_leave_draft_unchanged(self):
        invalid = [
            {self.item.pk: D("19")},
            {uuid.uuid4(): D("20")},
            {self.item.pk: D("20.001")},
            {self.item.pk: D("NaN")},
        ]
        for costs in invalid:
            with self.subTest(costs=costs), self.assertRaises(ValidationError):
                confirm_purchase(
                    owner=self.owner,
                    purchase_id=self.purchase.pk,
                    manual_allocations=costs,
                )
        self.purchase.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.purchase.status, "draft")
        self.assertIsNone(self.item.allocated_cost)
        self.assertEqual(self.material.physical_stock, 0)

    def test_zero_price_items_can_allocate_freight_manually(self):
        purchase = Purchase.objects.create(
            owner=self.owner, date=timezone.localdate(), freight=D("7")
        )
        item = add_item(
            owner=self.owner,
            purchase_id=purchase.pk,
            material_id=self.material.pk,
            quantity=D("10"),
            unit_price=D("0"),
        )
        confirm_purchase(
            owner=self.owner,
            purchase_id=purchase.pk,
            manual_allocations={item.pk: D("7")},
        )
        item.refresh_from_db()
        self.assertEqual(item.allocated_cost, D("7"))

    def test_allocation_view_checks_owner_and_validation(self):
        from django.urls import reverse

        url = reverse("purchasing:allocation", args=[self.purchase.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"mode": "manual"}).status_code, 404)
        self.client.force_login(self.owner)
        invalid = self.client.post(
            url, {"mode": "manual", f"cost_{self.item.pk}": "19"}
        )
        self.assertContains(invalid, "A soma")
        valid = self.client.post(url, {"mode": "manual", f"cost_{self.item.pk}": "20"})
        self.assertEqual(valid.status_code, 302)
