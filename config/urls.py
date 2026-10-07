from django.contrib.auth import views as auth
from django.urls import include, path
from accounts.views import dashboard, signup

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("conta/criar/", signup, name="signup"),
    path("conta/entrar/", auth.LoginView.as_view(), name="login"),
    path("conta/sair/", auth.LogoutView.as_view(), name="logout"),
    path("conta/recuperar/", auth.PasswordResetView.as_view(), name="password_reset"),
    path("conta/recuperar/enviado/", auth.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("conta/redefinir/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("conta/redefinir/concluido/", auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("materiais/", include("materials.urls")),
    path("precificacao/", include("pricing.urls")),
]
