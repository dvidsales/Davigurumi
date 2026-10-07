from decimal import Decimal
from django import forms
from materials.models import Material


class ProjectForm(forms.Form):
    reference_policy = forms.ChoiceField(
        label="Referência de custo dos materiais",
        required=False,
        initial="available",
        choices=[
            ("available", "Média do estoque disponível"),
            ("latest", "Última camada registrada"),
            ("manual", "Referência manual da ficha"),
        ],
        help_text="É uma estimativa. Consumos reais continuam usando o custo histórico da camada consumida.",
    )

    def clean_reference_policy(self):
        return self.cleaned_data.get("reference_policy") or "available"

    name = forms.CharField(label="Nome do projeto", max_length=160)
    description = forms.CharField(
        label="Descrição que pode ser apresentada ao cliente",
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    technique = forms.CharField(label="Técnica", max_length=100, required=False)
    base_quantity = forms.IntegerField(
        label="Quantidade-base da ficha", min_value=1, max_value=10000, initial=1
    )
    hours = forms.DecimalField(
        label="Horas estimadas para a quantidade-base",
        min_value=0,
        max_digits=8,
        decimal_places=2,
        initial=0,
    )
    hourly_rate = forms.DecimalField(
        label="Valor/hora (R$)", min_value=0, max_digits=10, decimal_places=2, initial=0
    )
    additional_cost = forms.DecimalField(
        label="Custos adicionais da quantidade-base (R$)",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
    )
    mode = forms.ChoiceField(
        label="Método", choices=[("markup", "Markup"), ("margin", "Margem")]
    )
    percentage = forms.DecimalField(
        label="Markup ou margem (%)",
        min_value=0,
        max_value=1000,
        decimal_places=2,
        initial=50,
    )
    fee = forms.DecimalField(
        label="Taxas (%)",
        min_value=0,
        max_value=Decimal("99.99"),
        decimal_places=2,
        initial=0,
    )
    notes = forms.CharField(
        label="Notas internas",
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class MaterialLineForm(forms.Form):
    material = forms.ModelChoiceField(
        label="Material", queryset=Material.objects.none()
    )
    quantity = forms.DecimalField(
        label="Quantidade para a quantidade-base da ficha",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )
    unit = forms.CharField(label="Unidade/embalagem", max_length=40, required=False)
    manual_unit_cost = forms.DecimalField(
        label="Referência manual por unidade base, se faltar custo (R$)",
        min_value=0,
        max_digits=12,
        decimal_places=6,
        required=False,
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            owner=owner, is_archived=False
        )


class AlternativeForm(forms.Form):
    material = forms.ModelChoiceField(
        label="Material alternativo", queryset=Material.objects.none()
    )
    quantity = forms.DecimalField(
        label="Quantidade alternativa na unidade base",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )
    note = forms.CharField(
        label="Diferenças e cuidados", max_length=200, required=False
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            owner=owner, is_archived=False
        )
