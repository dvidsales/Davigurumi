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
    new_supplier_name = forms.CharField(
        label="Nome do novo fornecedor", max_length=160, required=False
    )
    new_supplier_contact = forms.CharField(
        label="Contato do novo fornecedor", max_length=160, required=False
    )

    class Meta:
        model = Purchase
        fields = ("supplier", "date", "freight", "discount", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, owner, contact_query="", **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.partners import contact_choices

        contact_choices(self, "supplier", Supplier, owner, contact_query)
        self.fields["supplier"].label = "Fornecedor já cadastrado"
        if not self.instance._state.adding:
            self.fields.pop("new_supplier_name")
            self.fields.pop("new_supplier_contact")
        self.fields["date"].initial = timezone.localdate()
        for name in ("freight", "discount"):
            self.fields[name].min_value = Decimal(0)

    def clean(self):
        from accounts.partners import validate_contact

        return validate_contact(super().clean(), "supplier")


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
        self.fields["material"].queryset = Material.objects.filter(
            owner=owner, is_archived=False
        )


class ReceiveForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    quantity = forms.DecimalField(
        label="Quantidade efetivamente recebida na unidade base",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )


class AllocationForm(forms.Form):
    mode = forms.ChoiceField(
        label="Método de rateio",
        choices=[
            ("auto", "Proporcional ao valor dos itens"),
            ("manual", "Custo final informado por item"),
        ],
    )

    def __init__(self, *args, purchase, **kwargs):
        super().__init__(*args, **kwargs)
        self.purchase = purchase
        self.items = list(purchase.items.select_related("material").order_by("id"))
        for item in self.items:
            self.fields["cost_" + str(item.pk)] = forms.DecimalField(
                label=f"{item.material.name} — custo final de {item.quantity} {item.unit} (R$)",
                required=False,
                min_value=0,
                max_digits=12,
                decimal_places=2,
                initial=item.net_total,
            )

    def clean(self):
        data = super().clean()
        if data.get("mode") == "manual":
            costs = []
            for item in self.items:
                field = "cost_" + str(item.pk)
                value = data.get(field)
                if value is None:
                    self.add_error(field, "Informe o custo final deste item.")
                else:
                    costs.append(value)
            if (
                len(costs) == len(self.items)
                and sum(costs, Decimal(0)) != self.purchase.total
            ):
                raise forms.ValidationError(
                    "A soma precisa ser exatamente o total da compra, incluindo frete e desconto."
                )
        return data

    def allocations(self):
        if self.cleaned_data["mode"] == "auto":
            return None
        return {
            item.pk: self.cleaned_data["cost_" + str(item.pk)] for item in self.items
        }
