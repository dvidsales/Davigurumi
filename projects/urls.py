from django.urls import path
from . import views

app_name = "projects"
urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.create, name="create"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/editar/", views.edit, name="edit"),
    path("<uuid:pk>/material/", views.material, name="material"),
    path("linhas/<uuid:pk>/alternativa/", views.alternative, name="alternative"),
    path("linhas/<uuid:pk>/editar/", views.edit_line, name="edit_line"),
]
