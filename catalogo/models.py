import re
import unicodedata

from django.db import models


def clave(numero):
    """Número de parte sin guiones ni espacios, para comparar lo que escribe la gente (gp149 = GP-149)."""
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", numero or "").upper())


def clave_vehiculo(marca, modelo):
    # Marca y modelo juntos, para que "crv", "cr-v" y "honda crv" encuentren lo mismo.
    return " ".join([clave(marca), clave(modelo)]) + " " + clave(marca + modelo)


class TipoPieza(models.TextChoices):
    ACEITE = "ACEITE", "Filtro de aceite"
    ACEITE_SINT = "ACEITE_SINT", "Filtro de aceite para sintético"
    AIRE = "AIRE", "Filtro de aire"
    GASOLINA = "GASOLINA", "Filtro de gasolina"
    CABINA = "CABINA", "Filtro de cabina"


class Vehiculo(models.Model):
    marca = models.CharField(max_length=60, db_index=True)
    modelo = models.CharField(max_length=80, db_index=True)
    anio_inicio = models.PositiveSmallIntegerField("año inicial")
    anio_fin = models.PositiveSmallIntegerField("año final")
    motor = models.CharField(max_length=60, help_text="Ej. L4-1.6L, V8-5.3L")
    busqueda = models.CharField(max_length=160, db_index=True, editable=False)

    class Meta:
        ordering = ["marca", "modelo", "-anio_fin", "motor"]
        verbose_name = "vehículo"
        constraints = [
            models.UniqueConstraint(fields=["marca", "modelo", "anio_inicio", "anio_fin", "motor"], name="vehiculo_unico")
        ]

    def __str__(self):
        return f"{self.marca} {self.modelo} {self.anios} {self.motor}".strip()

    def save(self, *args, **kwargs):
        self.busqueda = clave_vehiculo(self.marca, self.modelo)
        super().save(*args, **kwargs)

    @property
    def anios(self):
        if self.anio_inicio == self.anio_fin:
            return str(self.anio_inicio)
        return f"{self.anio_inicio}–{self.anio_fin}"


class Aplicacion(models.Model):
    """Qué número Gonher lleva un vehículo, tal como viene en el catálogo del fabricante."""

    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name="vehículo")
    tipo = models.CharField(max_length=12, choices=TipoPieza.choices)
    numero_gonher = models.CharField("número Gonher", max_length=40, db_index=True)
    clave = models.CharField(max_length=40, db_index=True, editable=False)
    fuente = models.CharField(max_length=120, default="Catálogo Gonher 2026")

    class Meta:
        ordering = ["tipo", "numero_gonher"]
        verbose_name = "aplicación"
        verbose_name_plural = "aplicaciones"
        constraints = [models.UniqueConstraint(fields=["vehiculo", "tipo", "numero_gonher"], name="aplicacion_unica")]

    def __str__(self):
        return f"{self.vehiculo} · {self.get_tipo_display()} {self.numero_gonher}"

    def save(self, *args, **kwargs):
        self.clave = clave(self.numero_gonher)
        super().save(*args, **kwargs)


class Equivalencia(models.Model):
    """Un número de otra marca que sustituye a un número Gonher."""

    class Confianza(models.TextChoices):
        FABRICANTE = "FABRICANTE", "Tabla del fabricante"
        DOS_FUENTES = "DOS_FUENTES", "Coinciden dos fuentes"
        UNA_FUENTE = "UNA_FUENTE", "Una sola fuente, por confirmar"

    numero_gonher = models.CharField("número Gonher", max_length=40, db_index=True)
    marca = models.CharField(max_length=40)
    numero = models.CharField("número", max_length=40)
    clave = models.CharField(max_length=40, db_index=True, editable=False)
    confianza = models.CharField(max_length=12, choices=Confianza.choices)
    fuente = models.CharField(max_length=500, help_text="Documento o URL de donde salió")

    class Meta:
        ordering = ["marca", "numero"]
        verbose_name_plural = "equivalencias"
        constraints = [models.UniqueConstraint(fields=["numero_gonher", "marca", "numero"], name="equivalencia_unica")]

    def __str__(self):
        return f"{self.marca} {self.numero} = Gonher {self.numero_gonher}"

    def save(self, *args, **kwargs):
        self.clave = clave(self.numero)
        super().save(*args, **kwargs)

    @property
    def confirmada(self):
        return self.confianza != self.Confianza.UNA_FUENTE


class ConsultaPendiente(models.Model):
    """Lo que alguien preguntó y el catálogo no supo contestar: es la lista de datos por cargar."""

    class Canal(models.TextChoices):
        MOSTRADOR = "MOSTRADOR", "Buscador del mostrador"
        ASISTENTE = "ASISTENTE", "Asistente"

    texto = models.CharField(max_length=300)
    canal = models.CharField(max_length=10, choices=Canal.choices)
    creada = models.DateTimeField(auto_now_add=True)
    atendida = models.BooleanField(default=False)

    class Meta:
        ordering = ["atendida", "-creada"]
        verbose_name = "consulta pendiente"
        verbose_name_plural = "consultas pendientes"

    def __str__(self):
        return self.texto
