from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField("descripción", max_length=200, blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "categoría"

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Ubicacion(models.Model):
    codigo = models.CharField("código", max_length=20, unique=True, help_text="Ej. A-01-2 (pasillo, estante, nivel)")
    descripcion = models.CharField("descripción", max_length=120, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "ubicación"
        verbose_name_plural = "ubicaciones"

    def __str__(self):
        return self.codigo


class ProductoQuerySet(models.QuerySet):
    def con_stock(self):
        return self.annotate(stock=Coalesce(Sum("existencias__cantidad"), 0))


class Producto(models.Model):
    codigo = models.CharField("código", max_length=30, unique=True)
    codigo_barras = models.CharField("código de barras", max_length=40, unique=True, null=True, blank=True)
    numero_parte = models.CharField(
        "número de parte", max_length=40, blank=True, db_index=True,
        help_text="El del fabricante, ej. GP-149 o PH7317. Une el producto con el catálogo de aplicaciones.",
    )
    nombre = models.CharField(max_length=160)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos", verbose_name="categoría")
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name="productos")
    presentacion = models.CharField("presentación", max_length=40, blank=True, help_text="Ej. 946 ml, 4.73 L, pieza")
    especificacion = models.CharField(
        "especificación", max_length=60, blank=True, help_text="Viscosidad o norma, ej. 5W-30, API SP, DOT 4"
    )
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_venta = models.DecimalField("precio de venta", max_digits=10, decimal_places=2, default=0)
    punto_reorden = models.PositiveIntegerField("punto de reorden", default=5)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = ProductoQuerySet.as_manager()

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    def save(self, *args, **kwargs):
        if not self.codigo_barras:
            self.codigo_barras = None
        self.numero_parte = self.numero_parte.strip().upper()
        super().save(*args, **kwargs)

    def stock_total(self):
        return self.existencias.aggregate(t=Coalesce(Sum("cantidad"), 0))["t"]


class Existencia(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="existencias")
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="existencias", verbose_name="ubicación")
    cantidad = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["producto", "ubicacion"], name="existencia_unica")]
        ordering = ["ubicacion__codigo"]

    def __str__(self):
        return f"{self.producto.codigo} en {self.ubicacion}: {self.cantidad}"


class Movimiento(models.Model):
    class Tipo(models.TextChoices):
        ALTA = "ALTA", "Alta"
        BAJA = "BAJA", "Baja"

    class Motivo(models.TextChoices):
        COMPRA = "COMPRA", "Compra a proveedor"
        DEVOLUCION_CLIENTE = "DEV_CLIENTE", "Devolución de cliente"
        VENTA = "VENTA", "Venta"
        DANADO = "DANADO", "Producto dañado"
        CADUCADO = "CADUCADO", "Producto caducado"
        DEVOLUCION_PROVEEDOR = "DEV_PROVEEDOR", "Devolución a proveedor"
        USO_INTERNO = "USO_INTERNO", "Uso interno"
        AJUSTE = "AJUSTE", "Ajuste de inventario"

    MOTIVOS_ALTA = [Motivo.COMPRA, Motivo.DEVOLUCION_CLIENTE, Motivo.AJUSTE]
    MOTIVOS_BAJA = [
        Motivo.VENTA,
        Motivo.DANADO,
        Motivo.CADUCADO,
        Motivo.DEVOLUCION_PROVEEDOR,
        Motivo.USO_INTERNO,
        Motivo.AJUSTE,
    ]

    tipo = models.CharField(max_length=4, choices=Tipo.choices)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos")
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="movimientos", verbose_name="ubicación")
    cantidad = models.PositiveIntegerField()
    motivo = models.CharField(max_length=15, choices=Motivo.choices)
    referencia = models.CharField(max_length=60, blank=True, help_text="Factura, ticket o folio")
    notas = models.CharField(max_length=250, blank=True)
    stock_resultante = models.PositiveIntegerField(help_text="Stock total del producto después del movimiento")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos")
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad} × {self.producto.codigo}"


class Auditoria(models.Model):
    """Conteo físico de una ubicación. Al cerrarla, las diferencias se vuelven movimientos de ajuste."""

    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="auditorias", verbose_name="ubicación")
    abierta = models.BooleanField(default=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="auditorias")
    creada = models.DateTimeField(auto_now_add=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name = "auditoría"
        constraints = [
            models.UniqueConstraint(fields=["ubicacion"], condition=Q(abierta=True), name="una_auditoria_abierta_por_ubicacion")
        ]

    def __str__(self):
        return self.folio

    @property
    def folio(self):
        return f"AUD-{self.pk:05d}"


class LineaAuditoria(models.Model):
    auditoria = models.ForeignKey(Auditoria, on_delete=models.CASCADE, related_name="lineas")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="+")
    esperado = models.PositiveIntegerField(help_text="Lo que decía el sistema al abrir la auditoría")
    contado = models.PositiveIntegerField(null=True, blank=True)
    nota = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["producto__nombre"]
        constraints = [models.UniqueConstraint(fields=["auditoria", "producto"], name="producto_unico_por_auditoria")]

    @property
    def diferencia(self):
        return None if self.contado is None else self.contado - self.esperado


class AlertaReorden(models.Model):
    class Origen(models.TextChoices):
        REORDEN = "REORDEN", "Llegó al punto de reorden"
        SIN_STOCK = "SIN_STOCK", "Baja sin stock suficiente"

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ATENDIDA = "ATENDIDA", "Atendida"

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="alertas")
    origen = models.CharField(max_length=10, choices=Origen.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    stock_al_generar = models.PositiveIntegerField()
    punto_reorden = models.PositiveIntegerField()
    creada = models.DateTimeField(auto_now_add=True)
    notificada_en = models.DateTimeField(null=True, blank=True)
    atendida_en = models.DateTimeField(null=True, blank=True)
    atendida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas_atendidas"
    )

    class Meta:
        ordering = ["-creada"]
        verbose_name = "alerta de reorden"
        verbose_name_plural = "alertas de reorden"
        constraints = [
            models.UniqueConstraint(
                fields=["producto"], condition=Q(estado="PENDIENTE"), name="una_alerta_pendiente_por_producto"
            )
        ]

    def __str__(self):
        return f"Reorden {self.producto.codigo} ({self.get_estado_display()})"
