from django.contrib import admin

from .models import AlertaReorden, Categoria, Existencia, Marca, Movimiento, Producto, Ubicacion


class ExistenciaInline(admin.TabularInline):
    model = Existencia
    extra = 0
    readonly_fields = ["ubicacion", "cantidad"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "marca", "numero_parte", "categoria", "punto_reorden", "activo"]
    list_filter = ["categoria", "marca", "activo"]
    search_fields = ["codigo", "codigo_barras", "numero_parte", "nombre"]
    inlines = [ExistenciaInline]


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ["fecha", "tipo", "producto", "ubicacion", "cantidad", "motivo", "usuario"]
    list_filter = ["tipo", "motivo"]
    search_fields = ["producto__codigo", "producto__nombre", "referencia"]

    # El historial solo se escribe desde el flujo de altas y bajas.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AlertaReorden)
class AlertaReordenAdmin(admin.ModelAdmin):
    list_display = ["creada", "producto", "origen", "estado", "stock_al_generar", "notificada_en"]
    list_filter = ["estado", "origen"]


admin.site.register(Categoria)
admin.site.register(Marca)
admin.site.register(Ubicacion)
admin.site.site_header = "Refaccionaria · Administración"
