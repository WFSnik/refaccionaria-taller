from django.contrib import admin

from .models import Factura, Gasto, Pago


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ["folio", "receptor_nombre", "total", "estado", "fecha"]
    readonly_fields = ["orden", "subtotal", "iva", "total", "estado"]


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ["concepto", "categoria", "monto", "fecha"]
    list_filter = ["categoria"]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ["factura", "monto", "metodo", "fecha"]
    readonly_fields = ["factura", "monto"]
