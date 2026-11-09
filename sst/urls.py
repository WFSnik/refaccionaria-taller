from django.urls import path

from . import views

app_name = "sst"
urlpatterns = [
    path("", views.panel, name="panel"),
    path("orden/<int:orden_pk>/liberar/", views.liberar, name="liberar"),
    path("protocolos/nuevo/", views.protocolo_form, name="protocolo_crear"),
    path("protocolos/<int:pk>/editar/", views.protocolo_form, name="protocolo_editar"),
    path("protocolos/<int:protocolo_pk>/inspeccion/", views.inspeccion_crear, name="inspeccion_crear"),
    path("incidentes/nuevo/", views.incidente_crear, name="incidente_crear"),
    path("incidentes/<int:pk>/cerrar/", views.incidente_cerrar, name="incidente_cerrar"),
    path("epp/nuevo/", views.epp_crear, name="epp_crear"),
]
