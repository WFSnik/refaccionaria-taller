from django.urls import path

from . import views

app_name = "almacen"
urlpatterns = [
    path("", views.bandeja, name="bandeja"),
    path("existencias/", views.existencias, name="existencias"),
    path("solicitud/<int:pk>/entregar/", views.entregar, name="entregar"),
    path("solicitud/<int:pk>/cancelar/", views.cancelar_pendiente, name="cancelar_pendiente"),
    path("solicitud/<int:pk>/pedir/", views.pedir_faltante, name="pedir_faltante"),
    path("herramientas/", views.herramientas, name="herramientas"),
    path("herramientas/<int:pk>/prestar/", views.prestar, name="prestar"),
    path("prestamos/<int:pk>/devolver/", views.devolver, name="devolver"),
]
