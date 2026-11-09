from django.urls import path

from . import views

app_name = "contabilidad"
urlpatterns = [
    path("", views.resumen, name="resumen"),
    path("orden/<int:orden_pk>/facturar/", views.emitir, name="emitir"),
    path("facturas/", views.facturas, name="facturas"),
    path("facturas/<int:pk>/", views.factura, name="factura"),
    path("facturas/<int:pk>/imprimir/", views.imprimir, name="imprimir"),
    path("facturas/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("gastos/", views.gastos, name="gastos"),
    path("gastos/nuevo/", views.gasto_crear, name="gasto_crear"),
]
