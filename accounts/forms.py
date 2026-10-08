from django import forms
from django.conf import settings
from .invites import valid_invite
from django.contrib.auth.forms import UserCreationForm
from .models import User


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="E-mail")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.BETA_MODE:
            self.fields["invite_code"] = forms.CharField(
                label="Código do seu convite",
                max_length=128,
                widget=forms.PasswordInput,
            )

    def clean(self):
        data = super().clean()
        if settings.BETA_MODE and not valid_invite(
            data.get("email", ""), data.get("invite_code", "")
        ):
            self.add_error(
                None, "E-mail ou convite inválido. Consulte quem organizou o teste."
            )
        return data

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Este e-mail já possui uma conta. Entre ou recupere sua senha."
            )
        return email
