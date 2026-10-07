from django.urls import path
from . import views

app_name = "finance"
urlpatterns = [
    path("", views.index, name="index"),
    path("versoes/<uuid:pk>/recebimento/", views.payment, name="payment"),
    path("alocacoes/<uuid:pk>/estorno/", views.refund, name="refund"),
    path("pedidos/<uuid:pk>/parcela/", views.receivable, name="receivable"),
    path(
        "parcelas/<uuid:pk>/cancelar/",
        views.cancel_receivable,
        name="cancel_receivable",
    ),
]
