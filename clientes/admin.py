from django.contrib import admin

from .models import Cliente, VehiculoCliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nombre", "telefono", "correo", "rfc"]
    search_fields = ["nombre", "telefono", "rfc"]


@admin.register(VehiculoCliente)
class VehiculoClienteAdmin(admin.ModelAdmin):
    list_display = ["marca", "modelo", "anio", "placas", "cliente"]
    search_fields = ["placas", "vin", "marca", "modelo", "cliente__nombre"]
