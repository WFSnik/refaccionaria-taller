from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from inventario.seguridad import LoginLimitado

urlpatterns = [
    # El admin usa el mismo acceso con límite de intentos.
    path("admin/login/", LoginLimitado.as_view()),
    path("admin/", admin.site.urls),
    path("entrar/", LoginLimitado.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("vehiculos/", include("catalogo.urls")),
    path("asistente/", include("asistente.urls")),
    path("taller/", include("taller.urls")),
    path("clientes/", include("clientes.urls")),
    path("mostrador/", include("mostrador.urls")),
    path("ventas/", include("ventas.urls")),
    path("almacen/", include("almacen.urls")),
    path("compras/", include("proveedores.urls")),
    path("contabilidad/", include("contabilidad.urls")),
    path("seguridad/", include("sst.urls")),
    path("", include("inventario.urls")),
]
