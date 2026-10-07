import uuid
from decimal import Decimal
from django import forms
from .models import Material

class MaterialForm(forms.ModelForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    initial_quantity = forms.DecimalField(label="Quantidade que você já possui", min_value=0, max_digits=12,
        decimal_places=6, initial=0, help_text="Informe na unidade de estoque escolhida. Não cria uma compra.")
    initial_unit_cost = forms.DecimalField(label="Custo por g, m ou unidade", min_value=0, max_digits=12,
        decimal_places=6, required=False, help_text="Deixe em branco se desconhecido. Zero significa custo conhecido igual a zero.")

    class Meta:
        model = Material
        fields = ("name", "kind", "unit", "brand", "color", "color_code", "tex", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        data = super().clean()
        quantity = data.get("initial_quantity")
        if data.get("unit") == Material.Unit.PIECE and quantity is not None and quantity != quantity.to_integral_value():
            self.add_error("initial_quantity", "Materiais em unidades precisam de uma quantidade inteira.")
        if data.get("tex") is not None:
            if data["tex"] <= Decimal("0"):
                self.add_error("tex", "Tex deve ser maior que zero.")
            if data.get("kind") != Material.Kind.YARN:
                self.add_error("tex", "Preencha tex apenas para fios.")
        return data
