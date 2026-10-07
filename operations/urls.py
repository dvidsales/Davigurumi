from django.urls import path
from . import views

app_name = "operations"
urlpatterns = [
    path("", views.index, name="index"),
    path("relatorios/materiais/", views.material_report, name="material_report"),
    path("relatorios/", views.reports, name="reports"),
    path("<uuid:pk>/lida/", views.read, name="read"),
]
