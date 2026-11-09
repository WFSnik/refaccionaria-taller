from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat, name="asistente_chat"),
    path("mensaje/", views.mensaje, name="asistente_mensaje"),
    path("nueva/", views.nueva, name="asistente_nueva"),
]
