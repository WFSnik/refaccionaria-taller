from django.urls import path

from . import views

urlpatterns = [
    path("", views.vehiculos, name="catalogo_vehiculos"),
    path("opciones/", views.opciones, name="catalogo_opciones"),
    path("numero/", views.numero, name="catalogo_numero"),
    path("pendientes/", views.pendientes, name="catalogo_pendientes"),
    path("pendientes/<int:pk>/atender/", views.pendiente_atender, name="catalogo_pendiente_atender"),
]
