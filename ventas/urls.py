from django.urls import path

from . import views

app_name = "ventas"
urlpatterns = [
    path("", views.bandeja, name="bandeja"),
    path("orden/<int:orden_pk>/", views.presupuesto, name="presupuesto"),
    path("orden/<int:orden_pk>/cancelar/", views.cancelar, name="cancelar"),
    path("orden/<int:orden_pk>/terminar/", views.terminar, name="terminar"),
    path("linea/<int:pk>/quitar/", views.quitar_linea, name="quitar_linea"),
]
