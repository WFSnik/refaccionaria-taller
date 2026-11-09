from django.conf import settings
from django.db import models
from django.db.models import F, Sum

from taller.utils import totales


class Presupuesto(models.Model):
    class Medio(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "En persona"
        TELEFONO = "TELEFONO", "Por teléfono"
        MENSAJE = "MENSAJE", "Por mensaje"

    orden = models.OneToOneField("mostrador.OrdenTrabajo", on_delete=models.PROTECT, related_name="presupuesto")
    diagnostico = models.TextField("diagnóstico inicial", blank=True)
    autorizado_por = models.CharField("quién decidió", max_length=160, blank=True)
    medio = models.CharField(max_length=10, choices=Medio.choices, blank=True)
    decidido_en = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="presupuestos")
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Presupuesto de {self.orden.folio}"

    @property
    def editable(self):
        return self.orden.estado == "RECIBIDA"

    def montos(self):
        suma = self.lineas.aggregate(s=Sum(F("cantidad") * F("precio_unitario")))["s"] or 0
        subtotal, iva, total = totales(suma)
        return {"subtotal": subtotal, "iva": iva, "total": total}


class LineaPresupuesto(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name="lineas")
    # Con producto es una refacción que sale del almacén; sin producto es mano de obra o servicio.
    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    descripcion = models.CharField("descripción", max_length=200)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField("precio unitario", max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        verbose_name = "línea de presupuesto"
        verbose_name_plural = "líneas de presupuesto"

    def __str__(self):
        return self.descripcion

    @property
    def importe(self):
        return self.cantidad * self.precio_unitario
