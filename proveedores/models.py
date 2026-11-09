from django.conf import settings
from django.db import models


class Proveedor(models.Model):
    nombre = models.CharField(max_length=160, unique=True)
    rfc = models.CharField("RFC", max_length=13, blank=True)
    contacto = models.CharField(max_length=120, blank=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    correo = models.EmailField(blank=True)
    dias_entrega = models.PositiveSmallIntegerField("días de entrega", default=3)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "proveedores"

    def __str__(self):
        return self.nombre


class OrdenCompra(models.Model):
    class Estado(models.TextChoices):
        ENVIADA = "ENVIADA", "Enviada"
        PARCIAL = "PARCIAL", "Recibida en parte"
        RECIBIDA = "RECIBIDA", "Recibida"
        CANCELADA = "CANCELADA", "Cancelada"

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="ordenes")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ENVIADA)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name = "orden de compra"
        verbose_name_plural = "órdenes de compra"

    def __str__(self):
        return self.folio

    @property
    def folio(self):
        return f"OC-{self.pk:05d}"

    @property
    def total(self):
        return sum(linea.importe for linea in self.lineas.all())

    @property
    def color(self):
        return {"RECIBIDA": "ok", "CANCELADA": "agotado", "PARCIAL": "bajo"}.get(self.estado, "baja")


class LineaOrdenCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="lineas")
    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField()
    recibido = models.PositiveIntegerField(default=0)
    costo_unitario = models.DecimalField("costo unitario", max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["orden", "producto"], name="producto_unico_por_oc")]
        verbose_name = "línea de orden de compra"
        verbose_name_plural = "líneas de orden de compra"

    @property
    def pendiente(self):
        return self.cantidad - self.recibido

    @property
    def importe(self):
        return self.cantidad * self.costo_unitario


class SolicitudMaterial(models.Model):
    """Lo que almacén o las alertas de reorden le piden a compras."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_ORDEN = "EN_ORDEN", "En orden de compra"
        SURTIDA = "SURTIDA", "Surtida"
        CANCELADA = "CANCELADA", "Cancelada"

    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField()
    referencia = models.CharField(max_length=60, blank=True, help_text="Folio de la orden de trabajo o «Reorden»")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    orden_compra = models.ForeignKey(
        OrdenCompra, on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitudes"
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creada"]
        verbose_name = "solicitud de material"
        verbose_name_plural = "solicitudes de material"

    def __str__(self):
        return f"{self.cantidad} × {self.producto.codigo} ({self.get_estado_display()})"
