from django.contrib import admin

from .models import OrdenCompra, Proveedor, SolicitudMaterial

admin.site.register(Proveedor)
admin.site.register(SolicitudMaterial)


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ["folio", "proveedor", "estado", "creada"]
    readonly_fields = ["estado"]
