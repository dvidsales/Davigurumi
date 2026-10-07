import uuid
from decimal import Decimal
from django import forms
from django.utils import timezone


class PaymentForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    amount = forms.DecimalField(
        label="Valor efetivamente recebido (R$)",
        min_value=Decimal(".01"),
        max_digits=12,
        decimal_places=2,
    )
    date = forms.DateField(
        label="Data do recebimento",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    method = forms.ChoiceField(
        label="Meio",
        choices=[
            ("pix", "Pix"),
            ("cash", "Dinheiro"),
            ("transfer", "Transferência"),
            ("other", "Outro"),
        ],
    )
    notes = forms.CharField(label="Observações", max_length=200, required=False)
    allow_credit = forms.BooleanField(
        label="Reconheço que valor acima do devido gera crédito/excedente",
        required=False,
    )


class RefundForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    amount = forms.DecimalField(
        label="Valor efetivamente estornado/reembolsado (R$)",
        min_value=Decimal(".01"),
        max_digits=12,
        decimal_places=2,
    )
    date = forms.DateField(
        label="Data do estorno/reembolso",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    reason = forms.CharField(label="Motivo", max_length=200)


class ReceivableForm(forms.Form):
    amount = forms.DecimalField(
        label="Valor da cobrança prevista (R$)",
        min_value=Decimal(".01"),
        max_digits=12,
        decimal_places=2,
    )
    due_date = forms.DateField(
        label="Vencimento",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    label = forms.CharField(
        label="Identificação, como sinal ou parcela 1", max_length=100, required=False
    )
