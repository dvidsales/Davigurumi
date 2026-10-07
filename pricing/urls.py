from django.urls import path
from .views import calculator

app_name = "pricing"
urlpatterns = [path("", calculator, name="calculator")]
