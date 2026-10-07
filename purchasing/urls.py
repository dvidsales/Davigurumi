from django.urls import path
from . import views

app_name = "purchasing"
urlpatterns = [
    path("<uuid:pk>/rateio/", views.allocation, name="allocation"),
    path("", views.index, name="index"),
    path("nova/", views.create, name="create"),
    path("fornecedores/", views.suppliers, name="suppliers"),
    path("fornecedores/<uuid:pk>/", views.supplier_history, name="supplier_history"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/editar/", views.edit, name="edit"),
    path("<uuid:pk>/item/", views.item, name="item"),
    path("<uuid:pk>/acao/", views.action, name="action"),
    path("itens/<uuid:pk>/receber/", views.receive, name="receive"),
    path("itens/<uuid:pk>/editar/", views.edit_item, name="edit_item"),
]
