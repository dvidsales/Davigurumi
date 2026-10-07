from django.urls import path
from . import views

app_name = "portability"
urlpatterns = [
    path("", views.index, name="index"),
    path("previa/<uuid:job_id>/", views.preview, name="preview"),
    path("confirmar/<uuid:job_id>/", views.confirm, name="confirm"),
    path("materiais.<str:extension>", views.table_export, name="table_export"),
    path("completo/", views.archive, name="archive"),
]
