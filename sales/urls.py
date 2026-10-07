from django.urls import path
from . import views

app_name = "sales"
urlpatterns = [
    path("orcamentos/", views.index, name="index"),
    path("clientes/", views.clients, name="clients"),
    path("clientes/<uuid:pk>/", views.client_history, name="client_history"),
    path("orcamentos/novo/", views.create, name="create"),
    path("orcamentos/<uuid:pk>/comparar/", views.compare, name="compare"),
    path("orcamentos/<uuid:pk>/", views.detail, name="detail"),
    path("orcamentos/<uuid:pk>/nova-versao/", views.new_version, name="new_version"),
    path("versoes/<uuid:pk>/item/", views.item, name="item"),
    path("versoes/<uuid:pk>/publicar/", views.publish, name="publish"),
    path("versoes/<uuid:pk>/editar/", views.edit_version, name="edit_version"),
    path("itens/<uuid:pk>/editar/", views.edit_item, name="edit_item"),
    path("versoes/<uuid:pk>/link/", views.reissue, name="reissue"),
    path("versoes/<uuid:pk>/pdf/", views.owner_pdf, name="owner_pdf"),
    path("itens/<uuid:pk>/remover/", views.remove_item, name="remove_item"),
    path("portal/<str:raw>/", views.portal, name="portal"),
    path("portal/<str:raw>/pdf/", views.portal_pdf, name="portal_pdf"),
]
urlpatterns += [
    path("versoes/<uuid:pk>/revogar/", views.revoke, name="revoke"),
    path("versoes/<uuid:pk>/imagem/", views.image_upload, name="image_upload"),
    path("imagens/<uuid:pk>/", views.owner_image, name="owner_image"),
    path("imagens/<uuid:pk>/acao/", views.image_action, name="image_action"),
    path(
        "portal/<str:raw>/imagens/<uuid:pk>/", views.portal_image, name="portal_image"
    ),
]
