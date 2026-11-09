from django.contrib import admin

from .models import Aplicacion, ConsultaPendiente, Equivalencia, Vehiculo


class AplicacionInline(admin.TabularInline):
    model = Aplicacion
    extra = 0


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["marca", "modelo", "anio_inicio", "anio_fin", "motor"]
    list_filter = ["marca"]
    search_fields = ["marca", "modelo", "motor"]
    inlines = [AplicacionInline]


@admin.register(Equivalencia)
class EquivalenciaAdmin(admin.ModelAdmin):
    list_display = ["numero_gonher", "marca", "numero", "confianza"]
    list_filter = ["marca", "confianza"]
    search_fields = ["numero_gonher", "numero"]


@admin.register(ConsultaPendiente)
class ConsultaPendienteAdmin(admin.ModelAdmin):
    list_display = ["texto", "canal", "creada", "atendida"]
    list_filter = ["canal", "atendida"]
