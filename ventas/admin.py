from django.contrib import admin

from .models import LineaPresupuesto, Presupuesto


class LineaInline(admin.TabularInline):
    model = LineaPresupuesto
    extra = 0


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ["orden", "autorizado_por", "decidido_en"]
    inlines = [LineaInline]
