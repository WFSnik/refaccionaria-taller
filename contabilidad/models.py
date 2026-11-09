from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


class Factura(models.Model):
    """Comprobante interno de la venta. No es un CFDI: no está timbrado ante el SAT."""

    class Estado(models.TextChoices):
        EMITIDA = "EMITIDA", "Por cobrar"
        PAGADA = "PAGADA", "Pagada"
        CANCELADA = "CANCELADA", "Cancelada"

    orden = models.ForeignKey("mostrador.OrdenTrabajo", on_delete=models.PROTECT, related_name="facturas")
    receptor_nombre = models.CharField("cliente", max_length=160)
    receptor_rfc = models.CharField("RFC", max_length=13, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField("IVA", max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.EMITIDA, db_index=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(fields=["orden"], condition=~Q(estado="CANCELADA"), name="una_factura_vigente_por_orden")
        ]

    def __str__(self):
        return self.folio

    @property
    def folio(self):
        return f"F-{self.pk:05d}"

    @property
    def pagado(self):
        return self.pagos.aggregate(s=Sum("monto"))["s"] or 0

    @property
    def saldo(self):
        return self.total - self.pagado

    @property
    def color(self):
        return {"PAGADA": "ok", "CANCELADA": "agotado"}.get(self.estado, "bajo")


class LineaFactura(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="lineas")
    descripcion = models.CharField("descripción", max_length=200)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField("precio unitario", max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    @property
    def importe(self):
        return self.cantidad * self.precio_unitario


class Pago(models.Model):
    class Metodo(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        TARJETA = "TARJETA", "Tarjeta"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"

    factura = models.ForeignKey(Factura, on_delete=models.PROTECT, related_name="pagos")
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo = models.CharField("método", max_length=15, choices=Metodo.choices)
    referencia = models.CharField(max_length=60, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha"]


class Gasto(models.Model):
    class Categoria(models.TextChoices):
        COMPRAS = "COMPRAS", "Compras a proveedores"
        SEGURIDAD = "SEGURIDAD", "Seguridad y EPP"
        NOMINA = "NOMINA", "Nómina"
        SERVICIOS = "SERVICIOS", "Renta y servicios"
        OTROS = "OTROS", "Otros"

    categoria = models.CharField("categoría", max_length=10, choices=Categoria.choices)
    concepto = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.localdate, db_index=True)
    referencia = models.CharField(max_length=60, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado"]

    def __str__(self):
        return f"{self.concepto}: ${self.monto}"
