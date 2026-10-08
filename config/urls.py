from django.contrib.auth import views as auth
from django.urls import include, path
from accounts.views import dashboard, signup, SafePasswordResetView
from .pwa import manifest, service_worker
from .health import health
from accounts import demo, security

urlpatterns = [
    path("healthz/", health, name="health"),
    path("manifest.webmanifest", manifest, name="manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("", dashboard, name="dashboard"),
    path("demo/", demo.index, name="demo"),
    path("demo/alternar/", demo.switch, name="demo_switch"),
    path("conta/seguranca/", security.index, name="account_security"),
    path("conta/senha/", auth.PasswordChangeView.as_view(), name="password_change"),
    path(
        "conta/senha/alterada/",
        auth.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("conta/criar/", signup, name="signup"),
    path("conta/entrar/", auth.LoginView.as_view(), name="login"),
    path("conta/sair/", auth.LogoutView.as_view(), name="logout"),
    path("conta/recuperar/", SafePasswordResetView.as_view(), name="password_reset"),
    path(
        "conta/recuperar/enviado/",
        auth.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "conta/redefinir/<uidb64>/<token>/",
        auth.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "conta/redefinir/concluido/",
        auth.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("materiais/", include("materials.urls")),
    path("precificacao/", include("pricing.urls")),
    path("compras/", include("purchasing.urls")),
    path("projetos/", include("projects.urls")),
    path("notificacoes/", include("operations.urls")),
    path("pedidos/", include("production.urls")),
    path("financeiro/", include("finance.urls")),
    path("dados/", include("portability.urls")),
    path("", include("sales.urls")),
]
