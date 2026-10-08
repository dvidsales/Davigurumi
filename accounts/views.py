from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import login
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from materials.models import Material
from .forms import SignupForm


@never_cache
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if not settings.PUBLIC_SIGNUP_ENABLED and not settings.BETA_MODE:
        return HttpResponse("Cadastro público desabilitado neste ambiente.", status=403)
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error(
                None,
                "Não foi possível criar a conta com esses dados. Revise usuário e e-mail.",
            )
        else:
            login(request, user)
            messages.success(
                request,
                "Sua conta está pronta. Comece pelos materiais que você já possui.",
            )
            return redirect("dashboard")
    return render(request, "accounts/signup.html", {"form": form})


@never_cache
@login_required
def dashboard(request):
    from operations.reporting import overview

    materials = Material.objects.filter(owner=request.user, is_archived=False)
    return render(
        request,
        "dashboard.html",
        {
            "summary": overview(request.user),
            "material_count": materials.count(),
            "unknown_cost_count": materials.filter(
                layers__unit_cost__isnull=True, layers__physical__gt=0
            )
            .distinct()
            .count(),
            "recent_materials": materials.order_by("-created_at")[:5],
        },
    )


class SafePasswordResetView(PasswordResetView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["console_email"] = (
            settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
        )
        return context

    def dispatch(self, request, *args, **kwargs):
        unavailable = (
            settings.EMAIL_BACKEND == "django.core.mail.backends.dummy.EmailBackend"
        )
        if unavailable:
            return render(
                request, "registration/password_reset_unavailable.html", status=503
            )
        return super().dispatch(request, *args, **kwargs)
