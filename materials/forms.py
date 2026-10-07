import uuid
from decimal import Decimal
from django import forms
from .models import Material


class MaterialForm(forms.ModelForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    initial_quantity = forms.DecimalField(
        label="Quantidade que você já possui",
        min_value=0,
        max_digits=12,
        decimal_places=6,
        initial=0,
        help_text="Informe na unidade de estoque escolhida. Não cria uma compra.",
    )
    initial_unit_cost = forms.DecimalField(
        label="Custo por g, m ou unidade",
        min_value=0,
        max_digits=12,
        decimal_places=6,
        required=False,
        help_text="Deixe em branco se desconhecido. Zero significa custo conhecido igual a zero.",
    )

    minimum_stock = forms.DecimalField(
        label="Estoque mínimo disponível",
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=6,
        initial=0,
        help_text="Na unidade de estoque. Zero desativa o alerta de mínimo; reservas reduzem o saldo disponível.",
    )

    def clean_minimum_stock(self):
        minimum = self.cleaned_data.get("minimum_stock") or Decimal(0)
        if (
            self.cleaned_data.get("unit") == Material.Unit.PIECE
            and minimum != minimum.to_integral_value()
        ):
            raise forms.ValidationError(
                "O mínimo de materiais em unidades precisa ser inteiro."
            )
        return minimum

    class Meta:
        model = Material
        fields = (
            "name",
            "kind",
            "unit",
            "brand",
            "color",
            "color_code",
            "tex",
            "composition",
            "thickness",
            "recommended_hook",
            "minimum_stock",
            "notes",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        data = super().clean()
        quantity = data.get("initial_quantity")
        if (
            data.get("unit") == Material.Unit.PIECE
            and quantity is not None
            and quantity != quantity.to_integral_value()
        ):
            self.add_error(
                "initial_quantity",
                "Materiais em unidades precisam de uma quantidade inteira.",
            )
        if data.get("tex") is not None:
            if data["tex"] <= Decimal("0"):
                self.add_error("tex", "Tex deve ser maior que zero.")
            if data.get("kind") != Material.Kind.YARN:
                self.add_error("tex", "Preencha tex apenas para fios.")
        return data


class StockActionForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    action = forms.ChoiceField(
        label="Operação",
        choices=[
            ("receive", "Entrada de estoque"),
            ("reserve", "Reservar para um trabalho"),
            ("consume", "Consumir disponível"),
            ("loss", "Registrar perda"),
        ],
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )
    unit = forms.CharField(
        label="Unidade ou embalagem",
        max_length=40,
        required=False,
        help_text="Deixe em branco para a unidade base. Ex.: kg ou novelo, se a conversão estiver cadastrada.",
    )
    unit_cost = forms.DecimalField(
        label="Custo por unidade base (somente entrada)",
        min_value=0,
        max_digits=12,
        decimal_places=6,
        required=False,
    )
    lot = forms.CharField(
        label="Lote de fabricação (somente entrada)", max_length=80, required=False
    )
    reason = forms.CharField(label="Motivo / identificação do trabalho", max_length=100)


class ConversionForm(forms.Form):
    name = forms.CharField(label="Nome da embalagem/apresentação", max_length=40)
    factor = forms.DecimalField(
        label="Quantidade na unidade base por embalagem",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )


class ReservationActionForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    action = forms.ChoiceField(
        label="Operação",
        choices=[
            ("consume", "Consumir parte da reserva"),
            ("release", "Liberar toda a reserva restante"),
        ],
    )
    quantity = forms.DecimalField(
        label="Quantidade a consumir na unidade base",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
        required=False,
    )

    def clean(self):
        data = super().clean()
        if data.get("action") == "consume" and data.get("quantity") is None:
            self.add_error("quantity", "Informe quanto foi realmente consumido.")
        return data


class MaterialEditForm(MaterialForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("request_key", "initial_quantity", "initial_unit_cost"):
            self.fields.pop(name)
        self.fields["unit"].disabled = True
        self.fields["unit"].help_text = (
            "A unidade base é preservada para manter movimentos, conversões e fichas consistentes."
        )
