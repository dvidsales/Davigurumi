import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from .forms import MaterialForm, MaterialEditForm
from .services import create_material


class PackageCostTests(TestCase):
    def form(self, **changes):
        data = {
            "request_key": uuid.uuid4(),
            "name": "Synthetic yarn",
            "kind": "yarn",
            "unit": "g",
            "initial_quantity": "100",
            "use_package_cost": "on",
            "package_cost": "25.00",
            "package_quantity": "100",
        }
        data.update(changes)
        return MaterialForm(data)

    def test_decimal_conversion_and_creation_do_not_create_purchase(self):
        form = self.form(package_cost="10", package_quantity="3")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["initial_unit_cost"], Decimal("3.333333"))
        owner = get_user_model().objects.create_user(
            username="package-test", email="package@example.test"
        )
        material = create_material(owner=owner, form=form)
        self.assertEqual(material.movements.get().unit_cost, Decimal("3.333333"))
        from purchasing.models import Purchase

        self.assertEqual(Purchase.objects.count(), 0)
        self.assertEqual(create_material(owner=owner, form=form).pk, material.pk)

    def test_known_zero_unknown_and_manual_cost(self):
        for changes, expected in (
            ({"package_cost": "0"}, Decimal(0)),
            ({"use_package_cost": "", "initial_unit_cost": ""}, None),
            ({"use_package_cost": "", "initial_unit_cost": ".17"}, Decimal(".17")),
        ):
            form = self.form(**changes)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["initial_unit_cost"], expected)

    def test_invalid_incomplete_unit_fraction_and_out_of_precision(self):
        for changes in (
            {"package_quantity": "0"},
            {"package_cost": ""},
            {"package_quantity": ""},
            {"package_cost": "-1"},
            {"unit": "un", "package_quantity": "1.5"},
            {"package_cost": "9999999999.99", "package_quantity": ".000001"},
            {"package_cost": ".01", "package_quantity": "999999"},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.form(**changes).is_valid())
        self.assertNotIn("use_package_cost", MaterialEditForm().fields)
