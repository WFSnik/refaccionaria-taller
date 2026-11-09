from django.conf import settings
from django.db import models
from django.db.models import F, Q


class SolicitudPiezaQuerySet(models.QuerySet):
    def pendientes(self):
        return self.filter(cancelada=False, entregada__lt=F("cantidad"))


class SolicitudPieza(models.Model):
    orden = models.ForeignKey("mostrador.OrdenTrabajo", on_delete=models.PROTECT, related_name="solicitudes")
    linea = models.OneToOneField("ventas.LineaPresupuesto", on_delete=models.PROTECT, related_name="solicitud")
    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField()
    entregada = models.PositiveIntegerField(default=0)
    cancelada = models.BooleanField(default=False, help_text="Lo que faltaba por entregar ya no se ocupa.")
    creada = models.DateTimeField(auto_now_add=True)

    objects = SolicitudPiezaQuerySet.as_manager()

    class Meta:
        ordering = ["creada", "pk"]
        verbose_name = "solicitud de pieza"
        verbose_name_plural = "solicitudes de piezas"

    def __str__(self):
        return f"{self.orden.folio}: {self.cantidad} × {self.producto.codigo}"

    @property
    def pendiente(self):
        return 0 if self.cancelada else self.cantidad - self.entregada

    @property
    def estado(self):
        if self.pendiente == 0:
            return "Cerrada" if self.cancelada else "Entregada"
        return "Parcial" if self.entregada else "Pendiente"

    @property
    def color(self):
        return "ok" if self.pendiente == 0 else "bajo"


class EntregaMaterial(models.Model):
    solicitud = models.ForeignKey(SolicitudPieza, on_delete=models.PROTECT, related_name="entregas")
    movimiento = models.OneToOneField("inventario.Movimiento", on_delete=models.PROTECT, related_name="entrega_taller")
    recibio = models.CharField("quién recibe", max_length=120, help_text="Mecánico que recoge la pieza")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "entrega de material"
        verbose_name_plural = "entregas de material"


class Herramienta(models.Model):
    """Herramienta propia del taller: se presta a los mecánicos, no se vende ni entra al inventario de venta."""

    codigo = models.CharField("código", max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    ubicacion = models.CharField("ubicación", max_length=60, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    @property
    def prestamo_abierto(self):
        return next((p for p in self.prestamos.all() if p.devuelta is None), None)


class PrestamoHerramienta(models.Model):
    herramienta = models.ForeignKey(Herramienta, on_delete=models.PROTECT, related_name="prestamos")
    mecanico = models.CharField("mecánico", max_length=120)
    orden = models.ForeignKey(
        "mostrador.OrdenTrabajo", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="orden de trabajo",
    )
    salida = models.DateTimeField(auto_now_add=True)
    devuelta = models.DateTimeField(null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-salida"]
        verbose_name = "préstamo de herramienta"
        verbose_name_plural = "préstamos de herramientas"
        constraints = [
            models.UniqueConstraint(
                fields=["herramienta"], condition=Q(devuelta__isnull=True), name="un_prestamo_abierto_por_herramienta"
            )
        ]
