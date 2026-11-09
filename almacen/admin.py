from django.contrib import admin

from .models import Herramienta, PrestamoHerramienta, SolicitudPieza

admin.site.register(Herramienta)
admin.site.register(PrestamoHerramienta)


@admin.register(SolicitudPieza)
class SolicitudPiezaAdmin(admin.ModelAdmin):
    list_display = ["orden", "producto", "cantidad", "entregada", "cancelada"]
    readonly_fields = ["orden", "linea", "producto", "cantidad", "entregada"]
