from django.urls import path
from . import views

app_name = "materials"
urlpatterns = [path("", views.index, name="index"), path("novo/", views.create, name="create"),
               path("<uuid:pk>/", views.detail, name="detail")]
