from django.urls import path
from . import views

app_name = "materials"
urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/estoque/", views.stock_action, name="stock_action"),
    path("<uuid:pk>/arquivar/", views.archive, name="archive"),
    path("<uuid:pk>/editar/", views.edit, name="edit"),
    path("<uuid:pk>/conversao/", views.conversion, name="conversion"),
    path("movimentos/<uuid:pk>/compensar/", views.compensation, name="compensation"),
    path("reservas/<uuid:pk>/", views.reservation_action, name="reservation_action"),
]
