from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Protocolo(models.Model):
    nombre = models.CharField(max_length=160, unique=True)
    descripcion = models.CharField("descripción", max_length=250, blank=True)
    norma = models.CharField(max_length=40, blank=True, help_text="Ej. NOM-017-STPS-2008")
    frecuencia_dias = models.PositiveSmallIntegerField(
        "revisar cada (días)", default=30, help_text="0 si no requiere inspección periódica"
    )
    requerido_en_orden = models.BooleanField(
        "se verifica en cada orden", default=False, help_text="Debe confirmarse antes de iniciar una reparación"
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def ultima(self):
        return next(iter(self.inspecciones.all()), None)

    @property
    def vencido(self):
        if not self.frecuencia_dias:
            return False
        ultima = self.ultima
        return ultima is None or timezone.localdate() - ultima.fecha > timedelta(days=self.frecuencia_dias)


class Inspeccion(models.Model):
    class Resultado(models.TextChoices):
        CUMPLE = "CUMPLE", "Cumple"
        NO_CUMPLE = "NO_CUMPLE", "No cumple"

    protocolo = models.ForeignKey(Protocolo, on_delete=models.PROTECT, related_name="inspecciones")
    resultado = models.CharField(max_length=10, choices=Resultado.choices)
    observaciones = models.CharField(max_length=250, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-fecha", "-pk"]
        verbose_name = "inspección"
        verbose_name_plural = "inspecciones"


class LiberacionOrden(models.Model):
    """Cumplimiento normativo: seguridad confirma los protocolos antes de que inicie la reparación."""

    orden = models.OneToOneField("mostrador.OrdenTrabajo", on_delete=models.PROTECT, related_name="liberacion")
    protocolos = models.ManyToManyField(Protocolo, related_name="+", blank=True)
    notas = models.CharField(max_length=250, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "liberación de orden"
        verbose_name_plural = "liberaciones de órdenes"


class Incidente(models.Model):
    class Tipo(models.TextChoices):
        RIESGO = "RIESGO", "Riesgo detectado"
        INCIDENTE = "INCIDENTE", "Incidente"
        ACCIDENTE = "ACCIDENTE", "Accidente"

    class Severidad(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    severidad = models.CharField(max_length=5, choices=Severidad.choices)
    area = models.CharField("área", max_length=80)
    descripcion = models.TextField("descripción")
    accion_correctiva = models.TextField("acción correctiva", blank=True)
    cerrado = models.BooleanField(default=False)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    reportado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cerrado", "-creado"]

    def __str__(self):
        return f"{self.get_tipo_display()} en {self.area}"

    @property
    def color(self):
        return {"ALTA": "agotado", "MEDIA": "bajo"}.get(self.severidad, "baja")


class EntregaEPP(models.Model):
    empleado = models.CharField(max_length=120)
    equipo = models.CharField(max_length=120, help_text="Guantes, lentes, botas, respirador…")
    cantidad = models.PositiveSmallIntegerField(default=1)
    costo_total = models.DecimalField("costo total", max_digits=10, decimal_places=2, default=0)
    fecha = models.DateField(default=timezone.localdate)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-fecha", "-pk"]
        verbose_name = "entrega de EPP"
        verbose_name_plural = "entregas de EPP"
