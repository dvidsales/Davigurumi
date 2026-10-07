from django import forms
from .tables import COLUMNS


class TableImportForm(forms.Form):
    upload = forms.FileField(label="Arquivo CSV ou XLSX")
    locale = forms.ChoiceField(
        label="Formato dos números escritos como texto",
        choices=[
            ("pt-br", "Brasileiro: 1.000,25"),
            ("canonical", "Ponto decimal: 1000.25"),
        ],
    )
    separator = forms.ChoiceField(
        label="Separador do CSV",
        choices=[(";", "Ponto e vírgula"), (",", "Vírgula"), ("\t", "Tabulação")],
    )
    sheet = forms.CharField(
        label="Nome da aba (obrigatório se houver várias)",
        required=False,
        max_length=100,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in COLUMNS:
            self.fields["column_" + name] = forms.CharField(
                label="Coluna de " + name,
                initial=name,
                required=name in ("nome", "tipo", "unidade"),
                max_length=100,
            )

    def mapping(self):
        return {
            name: self.cleaned_data.get("column_" + name) or name for name in COLUMNS
        }


class ArchiveForm(forms.Form):
    password = forms.CharField(label="Confirme sua senha", widget=forms.PasswordInput)
    upload = forms.FileField(label="Pacote JSON completo", required=False)
    acknowledge = forms.BooleanField(
        label="Entendo que os links serão revogados e os aceites importados permanecerão apenas como histórico",
        required=False,
    )
