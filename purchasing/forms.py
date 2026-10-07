import uuid
from decimal import Decimal
from django import forms
from django.utils import timezone
from materials.models import Material
from .models import Purchase, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("name", "contact", "notes")


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ("supplier", "date", "freight", "discount", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(owner=owner)
        self.fields["date"].initial = timezone.localdate()
        for name in ("freight", "discount"):
            self.fields[name].min_value = Decimal(0)


class ItemForm(forms.Form):
    material = forms.ModelChoiceField(
        label="Material", queryset=Material.objects.none()
    )
    quantity = forms.DecimalField(
        label="Quantidade comprada",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )
    unit = forms.CharField(label="Unidade/embalagem", max_length=40, required=False)
    unit_price = forms.DecimalField(
        label="Preço por unidade/embalagem comprada (R$)",
        min_value=0,
        max_digits=12,
        decimal_places=2,
    )
    lot = forms.CharField(label="Lote de fabricação", max_length=80, required=False)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(owner=owner)


class ReceiveForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    quantity = forms.DecimalField(
        label="Quantidade efetivamente recebida na unidade base",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )
