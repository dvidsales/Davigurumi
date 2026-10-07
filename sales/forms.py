import uuid
from decimal import Decimal
from django import forms
from projects.models import Project, MaterialAlternative
from .models import QuoteVersion, Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ("name", "contact", "notes")


class QuoteForm(forms.Form):
    client = forms.ModelChoiceField(
        label="Cliente", queryset=Client.objects.none(), required=False
    )
    new_client_name = forms.CharField(
        label="Nome do novo cliente", max_length=160, required=False
    )
    new_client_contact = forms.CharField(
        label="Contato do novo cliente", max_length=160, required=False
    )
    terms = forms.CharField(
        label="Condições para o cliente",
        max_length=3000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    delivery_date = forms.DateField(
        label="Prazo de entrega/retirada",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    valid_days = forms.IntegerField(
        label="Validade em dias após publicação", min_value=1, max_value=365, initial=15
    )

    def __init__(self, *args, owner, contact_query="", **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.partners import contact_choices

        contact_choices(self, "client", Client, owner, contact_query)

    def clean(self):
        from accounts.partners import validate_contact

        return validate_contact(super().clean(), "client")


class QuoteItemForm(forms.Form):
    project = forms.ModelChoiceField(label="Projeto", queryset=Project.objects.none())
    quantity = forms.IntegerField(
        label="Quantidade de unidades produzidas",
        min_value=1,
        max_value=10000,
        initial=1,
    )
    description = forms.CharField(
        label="Descrição para o cliente (opcional)", max_length=300, required=False
    )
    manual_price = forms.DecimalField(
        label="Preço total manual deste item (R$), opcional",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        required=False,
    )
    discount = forms.DecimalField(
        label="Desconto percentual (%)",
        min_value=0,
        max_value=100,
        decimal_places=2,
        initial=0,
    )
    fixed_discount = forms.DecimalField(
        label="Desconto fixo deste item (R$)",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
    )

    def __init__(self, *args, owner, project_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(owner=owner)
        candidate = self.data.get("project") if self.is_bound else project_id
        try:
            selected = (
                Project.objects.filter(
                    pk=uuid.UUID(str(candidate)), owner=owner
                ).first()
                if candidate
                else None
            )
        except ValueError:
            selected = None
        if selected:
            self.fields["project"].initial = selected.pk
            for line in selected.current_revision.materials.select_related("material"):
                if line.alternatives.exists():
                    field = forms.ModelChoiceField(
                        label="Alternativa para " + line.material.name,
                        queryset=line.alternatives.select_related("material"),
                        required=False,
                        empty_label="Usar material original",
                    )
                    field.label_from_instance = (
                        lambda obj: f"{obj.material.name}: {obj.base_quantity} {obj.material.unit}"
                    )
                    self.fields["alternative_" + str(line.pk)] = field


class PublishForm(forms.Form):
    confirm_limitations = forms.BooleanField(
        label="Estou usando preço manual e reconheço que há custos desconhecidos",
        required=False,
    )
    confirm_below_cost = forms.BooleanField(
        label="Reconheço que o preço pode ficar abaixo do custo após taxas",
        required=False,
    )


class PortalForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    action = forms.ChoiceField(
        label="Sua decisão",
        choices=[
            ("approve", "Aprovar esta versão"),
            ("decline", "Recusar esta versão"),
            ("changes", "Solicitar alteração"),
        ],
    )
    declaration = forms.BooleanField(
        label="Li os itens, valores, condições e validade desta versão e confirmo minha decisão."
    )


class ImageForm(forms.Form):
    upload = forms.FileField(label="Imagem JPEG, PNG ou WebP (até 5 MB)")
    label = forms.CharField(label="Descrição da imagem", max_length=160)
    is_public = forms.BooleanField(
        label="Apresentar esta imagem ao cliente nesta versão", required=False
    )


class CompareForm(forms.Form):
    before = forms.ModelChoiceField(
        label="Versão anterior", queryset=QuoteVersion.objects.none()
    )
    after = forms.ModelChoiceField(
        label="Versão posterior", queryset=QuoteVersion.objects.none()
    )

    def __init__(self, *args, quote, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("before", "after"):
            self.fields[name].queryset = quote.versions.order_by("number")
            self.fields[name].label_from_instance = (
                lambda obj: f"Versão {obj.number} — {obj.get_status_display()}"
            )
