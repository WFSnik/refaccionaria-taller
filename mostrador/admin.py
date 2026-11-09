from django.contrib import admin

from .models import HistorialOrden, OrdenTrabajo


class HistorialInline(admin.TabularInline):
    model = HistorialOrden
    extra = 0
    readonly_fields = ["estado", "nota", "usuario", "fecha"]
    can_delete = False


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ["folio", "vehiculo", "estado", "creada"]
    list_filter = ["estado"]
    search_fields = ["vehiculo__placas", "vehiculo__cliente__nombre"]
    # El estado solo cambia por el flujo, para no saltarse sus reglas.
    readonly_fields = ["estado"]
    inlines = [HistorialInline]
