from decimal import Decimal
import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from .forms import MaterialForm
from .models import Material, StockMovement
from .services import create_material

class MaterialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = get_user_model().objects.create_user(username="ana", email="ana@example.test", password="Synthetic-Password-7!")
        cls.bia = get_user_model().objects.create_user(username="bia", email="bia@example.test", password="Synthetic-Password-8!")
        cls.private_material = Material.objects.create(owner=cls.bia, name="Material privado de Bia", kind="yarn", unit="g")

    def setUp(self):
        self.client.force_login(self.ana)

    def payload(self, **overrides):
        return {"name": "Fio azul", "kind": "yarn", "unit": "g", "brand": "Marca teste", "color": "Azul",
                "initial_quantity": "508", "initial_unit_cost": "0.100001", "request_key": str(uuid.uuid4()), **overrides}

    def test_duplicate_submission_returns_original_and_rejects_changed_payload(self):
        payload = self.payload()
        first = self.client.post(reverse("materials:create"), payload)
        second = self.client.post(reverse("materials:create"), payload)
        self.assertEqual(first.url, second.url)
        self.assertEqual(Material.objects.filter(owner=self.ana).count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)
        changed = self.client.post(reverse("materials:create"), payload | {"initial_quantity": "600"})
        self.assertContains(changed, "Este formulário já foi enviado com outros valores")
        self.assertEqual(Material.objects.get(owner=self.ana).physical_stock, Decimal("508"))

    def test_opening_is_exact_and_ignores_forged_owner(self):
        response = self.client.post(reverse("materials:create"), self.payload(owner=str(self.bia.pk)))
        material = Material.objects.get(name="Fio azul")
        self.assertRedirects(response, reverse("materials:detail", args=[material.pk]))
        self.assertEqual(material.owner, self.ana)
        self.assertEqual(material.physical_stock, Decimal("508"))
        self.assertEqual(material.movements.get().unit_cost, Decimal("0.100001"))
        self.assertEqual(material.movements.count(), 1)

    def test_unknown_cost_and_zero_cost_are_distinct(self):
        self.client.post(reverse("materials:create"), self.payload(name="Desconhecido", initial_unit_cost=""))
        self.client.post(reverse("materials:create"), self.payload(name="Grátis", initial_unit_cost="0"))
        self.assertIsNone(Material.objects.get(name="Desconhecido").movements.get().unit_cost)
        self.assertEqual(Material.objects.get(name="Grátis").movements.get().unit_cost, Decimal("0"))
        self.assertEqual(self.client.get(reverse("dashboard")).context["unknown_cost_count"], 1)

    def test_maximum_supported_decimal_is_preserved_after_database_reload(self):
        self.client.post(reverse("materials:create"), self.payload(initial_quantity="999999.999999", initial_unit_cost="999999.999999"))
        opening = Material.objects.get(name="Fio azul").movements.get()
        self.assertEqual(opening.quantity, Decimal("999999.999999"))
        self.assertEqual(opening.unit_cost, Decimal("999999.999999"))
        self.assertFalse(MaterialForm(self.payload(initial_quantity="1000000")).is_valid())

    def test_zero_stock_does_not_invent_purchase_or_movement(self):
        self.client.post(reverse("materials:create"), self.payload(initial_quantity="0"))
        self.assertFalse(Material.objects.get(name="Fio azul").movements.exists())

    def test_other_users_material_is_not_readable_or_searchable(self):
        self.assertEqual(self.client.get(reverse("materials:detail", args=[self.private_material.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("materials:index")), self.private_material.name)
        self.assertNotContains(self.client.get(reverse("materials:index"), {"q": "Bia"}), self.private_material.name)
        self.assertNotContains(self.client.get(reverse("dashboard")), self.private_material.name)

    def test_anonymous_private_routes_redirect_to_login(self):
        self.client.logout()
        for name in ("dashboard", "materials:index", "materials:create", "pricing:calculator"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_negative_fractional_discrete_and_overprecision_quantities_are_rejected(self):
        for values in ({"initial_quantity": "-1"}, {"unit": "un", "initial_quantity": "1.5"}, {"initial_quantity": "0.0000001"}):
            with self.subTest(values=values):
                form = MaterialForm(self.payload(**values))
                self.assertFalse(form.is_valid())

    def test_tex_only_applies_to_yarn_and_is_positive(self):
        for values in ({"kind": "packaging", "tex": "10"}, {"tex": "0"}):
            self.assertFalse(MaterialForm(self.payload(**values)).is_valid())
        self.assertTrue(MaterialForm(self.payload(tex="492")).is_valid())

    def test_atomic_creation_rolls_back_on_opening_failure(self):
        form = MaterialForm(self.payload())
        self.assertTrue(form.is_valid())
        with patch("materials.services.StockMovement.save", side_effect=RuntimeError("simulated write failure")):
            with self.assertRaises(RuntimeError):
                create_material(form=form, owner=self.ana)
        self.assertFalse(Material.objects.filter(name="Fio azul").exists())

    def test_database_rejects_negative_or_duplicate_opening(self):
        for quantity in (Decimal("-1"), Decimal("0")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                StockMovement.objects.create(material=self.private_material, quantity=quantity)
        StockMovement.objects.create(material=self.private_material, quantity=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.create(material=self.private_material, quantity=1)

    def test_private_notes_are_html_escaped(self):
        self.client.post(reverse("materials:create"), self.payload(notes="<script>alert(1)</script>"))
        material = Material.objects.get(name="Fio azul")
        response = self.client.get(reverse("materials:detail", args=[material.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")

    def test_search_and_pagination(self):
        Material.objects.bulk_create([Material(owner=self.ana, name=f"Fio teste {number:02}", kind="yarn", unit="g") for number in range(21)])
        first = self.client.get(reverse("materials:index"), {"q": "teste"}).context["page_obj"]
        self.assertEqual(len(first.object_list), 20)
        self.assertTrue(first.has_next())
        second = self.client.get(reverse("materials:index"), {"q": "teste", "page": 2}).context["page_obj"]
        self.assertEqual(len(second.object_list), 1)
