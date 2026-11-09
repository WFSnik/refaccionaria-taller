from django.urls import path

from . import views

app_name = "proveedores"
urlpatterns = [
    path("", views.bandeja, name="bandeja"),
    path("solicitud/nueva/", views.solicitud_manual, name="solicitud_manual"),
    path("alerta/<int:pk>/solicitar/", views.desde_alerta, name="desde_alerta"),
    path("ordenes/", views.ordenes, name="ordenes"),
    path("ordenes/nueva/", views.orden_crear, name="orden_crear"),
    path("ordenes/<int:pk>/", views.orden_detalle, name="orden_detalle"),
    path("ordenes/<int:pk>/cancelar/", views.orden_cancelar, name="orden_cancelar"),
    path("directorio/", views.proveedores, name="proveedores"),
    path("directorio/nuevo/", views.proveedor_form, name="proveedor_crear"),
    path("directorio/<int:pk>/editar/", views.proveedor_form, name="proveedor_editar"),
]
