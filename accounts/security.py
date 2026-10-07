"""Password-confirmed account controls. Suspension preserves retained history."""

import uuid
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import DemoWorkspace
from materials.stock import begin_operation, finish
from sales.models import ShareToken
from operations.models import AuditEvent


class AccountSecurityForm(forms.Form):
    key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    password = forms.CharField(
        label="Confirme sua senha atual", widget=forms.PasswordInput
    )
    acknowledge = forms.BooleanField(
        label="Entendo que os links serão revogados e que suspender impede novos acessos, sem eliminar o histórico"
    )
    reason = forms.CharField(label="Motivo", max_length=200)


@transaction.atomic
def account_action(*, owner, password, key, reason, action):
    current = get_user_model().objects.select_for_update().get(pk=owner.pk)
    if not current.check_password(password):
        raise ValidationError("Senha incorreta.")
    if action not in {"revoke", "suspend"} or not reason.strip() or len(reason) > 200:
        raise ValidationError("Operação ou motivo inválido.")
    op, repeated = begin_operation(
        current, key, "account_security", {"action": action, "reason": reason}
    )
    if repeated:
        return op.result
    workspace = DemoWorkspace.objects.filter(owner=current).first()
    identities = [current.pk] + ([workspace.demo_user_id] if workspace else [])
    count = ShareToken.objects.filter(
        version__quote__owner_id__in=identities, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    if action == "suspend":
        get_user_model().objects.filter(pk__in=identities).update(is_active=False)
    AuditEvent.objects.create(
        owner=current,
        action="account_suspended" if action == "suspend" else "all_links_revoked",
        object_id=current.pk,
        reason=reason,
    )
    return finish(op, {"revoked": count, "suspended": action == "suspend"})


@never_cache
@login_required
def index(request):
    form = AccountSecurityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data.copy()
        values.pop("acknowledge")
        try:
            result = account_action(
                owner=request.user, action=request.POST.get("action"), **values
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if result["suspended"]:
                logout(request)
                messages.success(
                    request,
                    "Acesso suspenso e links revogados. O histórico foi preservado; reativação depende de revisão administrativa.",
                )
                return redirect("login")
            messages.success(
                request,
                f"{result['revoked']} links revogados. Arquivos já baixados não são recolhidos.",
            )
            return redirect("account_security")
    return render(request, "accounts/security.html", {"form": form})
