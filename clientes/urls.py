from django.urls import path

from . import views

app_name = "clientes"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:cliente_pk>/vehiculos/nuevo/", views.vehiculo_crear, name="vehiculo_crear"),
    path("vehiculos/<int:pk>/editar/", views.vehiculo_editar, name="vehiculo_editar"),
]
