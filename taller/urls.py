from django.urls import path

from . import views

app_name = "taller"
urlpatterns = [
    path("", views.flujo, name="flujo"),
]
