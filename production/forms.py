import uuid
from decimal import Decimal
from django import forms
from materials.models import Material, StockReservation


class ConsumeForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    material = forms.ModelChoiceField(
        label="Material usado", queryset=Material.objects.none()
    )
    reservation = forms.ModelChoiceField(
        label="Usar uma reserva deste item (opcional)",
        queryset=StockReservation.objects.none(),
        required=False,
    )
    quantity = forms.DecimalField(
        label="Quantidade realmente usada na unidade base",
        min_value=Decimal(".000001"),
        max_digits=12,
        decimal_places=6,
    )

    def __init__(self, *args, owner, item, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(owner=owner)
        self.fields["reservation"].queryset = StockReservation.objects.filter(
            reference=item.pk, layer__material__owner=owner, remaining__gt=0
        ).select_related("layer__material")
        self.fields["reservation"].label_from_instance = (
            lambda obj: f"{obj.layer.material.name}: {obj.remaining} {obj.layer.material.unit}"
        )


class ManualTimeForm(forms.Form):
    minutes = forms.IntegerField(
        label="Minutos efetivamente trabalhados", min_value=0, max_value=43200
    )
    ended_at = forms.DateTimeField(
        label="Término do intervalo (opcional)",
        required=False,
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
    )


class CorrectionForm(forms.Form):
    minutes = forms.IntegerField(
        label="Duração corrigida em minutos", min_value=0, max_value=43200
    )
    reason = forms.CharField(label="Motivo da correção", max_length=200)


class ProducedForm(forms.Form):
    quantity = forms.IntegerField(
        label="Total produzido deste item até agora", min_value=0, max_value=10000
    )


class DeliveryForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    quantity = forms.IntegerField(
        label="Quantidade desta entrega", min_value=1, max_value=10000
    )
    notes = forms.CharField(
        label="Observações da entrega", max_length=200, required=False
    )


class OrderSettingsForm(forms.Form):
    production_due = forms.DateField(
        label="Prazo de produção",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    delivery_status = forms.ChoiceField(
        label="Situação da entrega",
        choices=[
            ("not_sent", "Não enviada"),
            ("ready", "Pronta para retirada"),
            ("sent", "Enviada"),
        ],
    )
