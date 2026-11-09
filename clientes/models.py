from django.db import models
from django.db.models import Q


class Cliente(models.Model):
    nombre = models.CharField(max_length=160)
    telefono = models.CharField("teléfono", max_length=20)
    correo = models.EmailField(blank=True)
    rfc = models.CharField("RFC", max_length=13, blank=True)
    notas = models.CharField(max_length=250, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.rfc = self.rfc.strip().upper()
        super().save(*args, **kwargs)


class VehiculoCliente(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="vehiculos")
    marca = models.CharField(max_length=60)
    modelo = models.CharField(max_length=60)
    anio = models.PositiveSmallIntegerField("año")
    placas = models.CharField(max_length=12, blank=True)
    vin = models.CharField("VIN", max_length=17, blank=True)
    color = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["marca", "modelo"]
        verbose_name = "vehículo de cliente"
        verbose_name_plural = "vehículos de clientes"
        constraints = [
            models.UniqueConstraint(fields=["placas"], condition=~Q(placas=""), name="placas_unicas"),
        ]

    def __str__(self):
        placas = f" · {self.placas}" if self.placas else ""
        return f"{self.marca} {self.modelo} {self.anio}{placas}"

    def save(self, *args, **kwargs):
        self.placas = self.placas.strip().upper()
        self.vin = self.vin.strip().upper()
        super().save(*args, **kwargs)
