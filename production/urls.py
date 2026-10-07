from django.urls import path
from . import views

app_name = "production"
urlpatterns = [
    path("", views.index, name="index"),
    path("aprovar/<uuid:pk>/pedido/", views.convert, name="convert"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/acao/", views.action, name="action"),
    path("<uuid:pk>/configuracao/", views.settings, name="settings"),
    path("itens/<uuid:pk>/iniciar/", views.start, name="start"),
    path("itens/<uuid:pk>/<str:action>/", views.item_action, name="item_action"),
    path("sessoes/<uuid:pk>/pausar/", views.stop, name="stop"),
    path("sessoes/<uuid:pk>/corrigir/", views.correction, name="correction"),
]
