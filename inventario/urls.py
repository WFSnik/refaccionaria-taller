from django.urls import path

from . import auditorias, views

urlpatterns = [
    path("auditorias/", auditorias.lista, name="auditorias"),
    path("auditorias/<int:pk>/", auditorias.detalle, name="auditoria_detalle"),
    path("", views.dashboard, name="dashboard"),
    path("productos/", views.productos_lista, name="productos_lista"),
    path("productos/nuevo/", views.producto_crear, name="producto_crear"),
    path("productos/<int:pk>/", views.producto_detalle, name="producto_detalle"),
    path("productos/<int:pk>/editar/", views.producto_editar, name="producto_editar"),
    path("movimientos/", views.movimientos_lista, name="movimientos_lista"),
    path("movimientos/nuevo/", views.movimiento_nuevo, name="movimiento_nuevo"),
    path("ubicaciones/", views.ubicaciones, name="ubicaciones"),
    path("alertas/", views.alertas, name="alertas"),
    path("alertas/<int:pk>/correo/", views.alerta_correo, name="alerta_correo"),
    path("alertas/<int:pk>/atender/", views.alerta_atender, name="alerta_atender"),
    path("api/productos/", views.api_productos, name="api_productos"),
]
