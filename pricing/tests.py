from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from .domain import calculate_price
from .forms import PricingForm

D = Decimal

class PricingDomainTests(SimpleTestCase):
    def test_prd_markup_50_and_margin_50(self):
        markup = calculate_price(cost=D("100"), mode="markup", percentage=D("0.5"))
        margin = calculate_price(cost=D("100"), mode="margin", percentage=D("0.5"))
        self.assertEqual(markup.sale_price, D("150.00"))
        self.assertEqual(round(markup.effective_margin * 100, 2), D("33.33"))
        self.assertEqual(margin.sale_price, D("200.00"))

    def test_prd_margin_with_fee(self):
        result = calculate_price(cost=D("100"), mode="margin", percentage=D(".30"), fee=D(".05"))
        self.assertEqual(result.sale_price, D("153.85"))

    def test_discount_order_and_effective_margin(self):
        result = calculate_price(cost=D("100"), mode="markup", percentage=D(".5"), discount=D(".1"), fixed_discount=D("5"))
        self.assertEqual(result.sale_price, D("130.00"))
        self.assertEqual(round(result.effective_margin * 100, 2), D("23.08"))

    def test_markup_fees_are_deducted_without_increasing_price(self):
        result = calculate_price(cost=D("100"), mode="markup", percentage=D(".5"), fee=D(".05"))
        self.assertEqual(result.sale_price, D("150.00"))
        self.assertEqual(result.profit, D("42.50"))

    def test_zero_price_has_undefined_margin_and_negative_profit(self):
        result = calculate_price(cost=D("100"), mode="markup", percentage=D("0"), discount=D("1"))
        self.assertIsNone(result.effective_margin)
        self.assertEqual(result.profit, D("-100.00"))

    def test_half_up_rounding(self):
        self.assertEqual(calculate_price(cost=D("1.005"), mode="markup", percentage=D("0")).sale_price, D("1.01"))

    def test_invalid_percentage_or_negative_price_is_rejected(self):
        for kwargs in ({"percentage": D("1"), "mode": "margin"}, {"percentage": D(".95"), "fee": D(".05"), "mode": "margin"},
            {"discount": D("1.01")}, {"fee": D("1")}, {"cost": D("-1")}, {"fixed_discount": D("200")}, {"mode": "other"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                calculate_price(**({"cost": D("100"), "mode": "markup", "percentage": D("0")} | kwargs))

    def test_nonfinite_values_and_floats_are_rejected(self):
        for value in (D("NaN"), D("Infinity"), 0.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_price(cost=value, mode="markup", percentage=D("0"))

    def test_fee_boundary_is_decimal(self):
        form = PricingForm({"materials_cost": "100", "hours": "0", "hourly_rate": "0", "additional_cost": "0",
                            "mode": "markup", "percentage": "50", "fee": "99.99", "discount": "0", "fixed_discount": "0"})
        self.assertTrue(form.is_valid(), form.errors)

class PricingViewTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username="ana", email="ana@example.test"))

    def test_view_combines_labor_materials_and_additional_cost(self):
        response = self.client.post(reverse("pricing:calculator"), {"materials_cost": "30", "hours": "2", "hourly_rate": "30",
            "additional_cost": "10", "mode": "markup", "percentage": "50", "fee": "0", "discount": "0", "fixed_discount": "0"})
        self.assertContains(response, "150,00")
        self.assertEqual(response.context["result"].cost, D("100.00"))

    def test_invalid_margin_shows_actionable_error(self):
        response = self.client.post(reverse("pricing:calculator"), {"materials_cost": "100", "hours": "0", "hourly_rate": "0",
            "additional_cost": "0", "mode": "margin", "percentage": "95", "fee": "5", "discount": "0", "fixed_discount": "0"})
        self.assertContains(response, "Margem e taxas somadas precisam ser menores")
        self.assertIsNone(response.context["result"])
