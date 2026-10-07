from decimal import Decimal
from django import forms

class PricingForm(forms.Form):
    materials_cost = forms.DecimalField(label="Materiais (R$)", min_value=0, max_digits=12, decimal_places=2, initial=0)
    hours = forms.DecimalField(label="Tempo estimado (horas)", min_value=0, max_digits=8, decimal_places=2, initial=0)
    hourly_rate = forms.DecimalField(label="Valor da sua hora (R$)", min_value=0, max_digits=10, decimal_places=2, initial=0)
    additional_cost = forms.DecimalField(label="Embalagem e outros custos (R$)", min_value=0, max_digits=12, decimal_places=2, initial=0)
    mode = forms.ChoiceField(label="Como calcular", choices=(("markup", "Markup sobre o custo"), ("margin", "Margem sobre a venda")))
    percentage = forms.DecimalField(label="Markup ou margem (%)", min_value=0, max_value=1000, decimal_places=2, initial=50)
    fee = forms.DecimalField(label="Taxas sobre a venda (%)", min_value=0, max_value=Decimal("99.99"), decimal_places=2, initial=0)
    discount = forms.DecimalField(label="Desconto percentual (%)", min_value=0, max_value=100, decimal_places=2, initial=0)
    fixed_discount = forms.DecimalField(label="Desconto fixo (R$)", min_value=0, max_digits=12, decimal_places=2, initial=0)
