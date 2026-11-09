from django.conf import settings
from django.db import models


class OrdenTrabajo(models.Model):
    class Estado(models.TextChoices):
        RECIBIDA = "RECIBIDA", "Recibida"
        PRESUPUESTADA = "PRESUPUESTADA", "Presupuesto enviado"
        AUTORIZADA = "AUTORIZADA", "Autorizada"
        EN_REPARACION = "EN_REPARACION", "En reparación"
        TERMINADA = "TERMINADA", "Terminada"
        FACTURADA = "FACTURADA", "Facturada"
        ENTREGADA = "ENTREGADA", "Entregada"
        RECHAZADA = "RECHAZADA", "Rechazada por el cliente"
        CANCELADA = "CANCELADA", "Cancelada"

    # Etapas que se ven en la barra de avance, en orden.
    AVANCE = [
        Estado.RECIBIDA, Estado.PRESUPUESTADA, Estado.AUTORIZADA, Estado.EN_REPARACION,
        Estado.TERMINADA, Estado.FACTURADA, Estado.ENTREGADA,
    ]
    ABIERTOS = [
        Estado.RECIBIDA, Estado.PRESUPUESTADA, Estado.AUTORIZADA,
        Estado.EN_REPARACION, Estado.TERMINADA, Estado.FACTURADA,
    ]

    vehiculo = models.ForeignKey(
        "clientes.VehiculoCliente", on_delete=models.PROTECT, related_name="ordenes", verbose_name="vehículo"
    )
    sintomas = models.TextField("síntomas", help_text="Lo que el cliente reporta, con sus palabras.")
    kilometraje = models.PositiveIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.RECIBIDA, db_index=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordenes_creadas")
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name = "orden de trabajo"
        verbose_name_plural = "órdenes de trabajo"

    def __str__(self):
        return self.folio

    @property
    def folio(self):
        return f"OT-{self.pk:05d}"

    @property
    def cliente(self):
        return self.vehiculo.cliente

    @property
    def color(self):
        if self.estado in (self.Estado.RECHAZADA, self.Estado.CANCELADA):
            return "agotado"
        if self.estado == self.Estado.ENTREGADA:
            return "ok"
        if self.estado in (self.Estado.TERMINADA, self.Estado.FACTURADA):
            return "alta"
        if self.estado == self.Estado.EN_REPARACION:
            return "baja"
        return "bajo"

    def pasos(self):
        """Etapas para la barra de avance; una orden rechazada o cancelada se queda donde iba."""
        if self.estado in self.AVANCE:
            actual = self.AVANCE.index(self.estado)
        else:
            actual = -1
        return [
            {"nombre": e.label, "clase": "hecho" if i < actual else "actual" if i == actual else ""}
            for i, e in enumerate(self.AVANCE)
        ]


class HistorialOrden(models.Model):
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name="historial")
    estado = models.CharField(max_length=15, choices=OrdenTrabajo.Estado.choices)
    nota = models.CharField(max_length=250, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]
        verbose_name = "historial de orden"
        verbose_name_plural = "historial de órdenes"
