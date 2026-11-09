"""Reglas del flujo de inventario: altas, bajas y alertas de reorden."""

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import AlertaReorden, Existencia, Movimiento, Producto


class StockInsuficiente(Exception):
    def __init__(self, disponible_ubicacion, disponible_total, alerta=None):
        self.disponible_ubicacion = disponible_ubicacion
        self.disponible_total = disponible_total
        self.alerta = alerta
        super().__init__(f"Solo hay {disponible_ubicacion} en esa ubicación ({disponible_total} en total).")


def _bloquear_producto(producto_id):
    # Serializa los movimientos de un mismo producto para que el stock total sea consistente.
    return Producto.objects.select_for_update().get(pk=producto_id)


@transaction.atomic
def registrar_alta(*, producto, ubicacion, cantidad, motivo, usuario, referencia="", notas=""):
    producto = _bloquear_producto(producto.pk)
    existencia, _ = Existencia.objects.select_for_update().get_or_create(producto=producto, ubicacion=ubicacion)
    existencia.cantidad += cantidad
    existencia.save(update_fields=["cantidad"])

    total = producto.stock_total()
    movimiento = Movimiento.objects.create(
        tipo=Movimiento.Tipo.ALTA,
        producto=producto,
        ubicacion=ubicacion,
        cantidad=cantidad,
        motivo=motivo,
        referencia=referencia,
        notas=notas,
        usuario=usuario,
        stock_resultante=total,
    )
    if total > producto.punto_reorden:
        # El reabasto cierra las alertas que seguían abiertas.
        AlertaReorden.objects.filter(producto=producto, estado=AlertaReorden.Estado.PENDIENTE).update(
            estado=AlertaReorden.Estado.ATENDIDA, atendida_en=timezone.now(), atendida_por=usuario
        )
        alerta = None
    else:
        alerta = generar_alerta(producto, total, AlertaReorden.Origen.REORDEN)
    return movimiento, alerta


def registrar_baja(*, producto, ubicacion, cantidad, motivo, usuario, referencia="", notas=""):
    with transaction.atomic():
        producto = _bloquear_producto(producto.pk)
        existencia = Existencia.objects.select_for_update().filter(producto=producto, ubicacion=ubicacion).first()
        en_ubicacion = existencia.cantidad if existencia else 0
        total = producto.stock_total()

        if cantidad <= en_ubicacion:
            existencia.cantidad -= cantidad
            existencia.save(update_fields=["cantidad"])
            total -= cantidad
            movimiento = Movimiento.objects.create(
                tipo=Movimiento.Tipo.BAJA,
                producto=producto,
                ubicacion=ubicacion,
                cantidad=cantidad,
                motivo=motivo,
                referencia=referencia,
                notas=notas,
                usuario=usuario,
                stock_resultante=total,
            )
            alerta = None
            if total <= producto.punto_reorden:
                alerta = generar_alerta(producto, total, AlertaReorden.Origen.REORDEN)
            return movimiento, alerta

    # Sin stock suficiente la baja no se registra. Si falta en el total
    # (no solo en esta ubicación) se avisa a compras.
    alerta = None
    if cantidad > total:
        alerta = generar_alerta(producto, total, AlertaReorden.Origen.SIN_STOCK)
    raise StockInsuficiente(en_ubicacion, total, alerta)


def generar_alerta(producto, stock, origen):
    """Crea la alerta pendiente del producto (solo una a la vez) y notifica a compras."""
    alerta = AlertaReorden.objects.filter(producto=producto, estado=AlertaReorden.Estado.PENDIENTE).first()
    if alerta:
        return alerta
    try:
        with transaction.atomic():
            alerta = AlertaReorden.objects.create(
                producto=producto, origen=origen, stock_al_generar=stock, punto_reorden=producto.punto_reorden
            )
    except IntegrityError:
        return AlertaReorden.objects.get(producto=producto, estado=AlertaReorden.Estado.PENDIENTE)

    transaction.on_commit(lambda: notificar_compras(alerta.pk))
    return alerta


def contexto_correo(alerta):
    """Datos del correo de reorden; lo usan el envío y la vista previa."""
    p = alerta.producto
    stock = alerta.stock_al_generar
    reorden = alerta.punto_reorden
    # Se sugiere pedir hasta 3 veces el punto de reorden: el mismo "lleno" que usa la bayoneta.
    objetivo = max(reorden * 3, 1)
    sugerido = max(objetivo - stock, reorden, 1)
    return {
        "alerta": alerta,
        "producto": p,
        "stock": stock,
        "reorden": reorden,
        "sugerido": sugerido,
        "costo_estimado": sugerido * p.costo,
        "pct": min(round(stock / objetivo * 100), 100),
        "reorden_pct": min(round(reorden / objetivo * 100), 100),
        "existencias": p.existencias.filter(cantidad__gt=0).select_related("ubicacion"),
        "salidas": p.movimientos.filter(tipo="BAJA").select_related("ubicacion")[:4],
        "url_producto": f"{settings.SITIO_URL}{reverse('producto_detalle', args=[p.pk])}",
        "url_alertas": f"{settings.SITIO_URL}{reverse('alertas')}",
    }


def notificar_compras(alerta_id):
    alerta = AlertaReorden.objects.select_related("producto__marca", "producto__categoria").get(pk=alerta_id)
    p = alerta.producto
    contexto = contexto_correo(alerta)
    enviados = send_mail(
        subject=f"Reordenar {p.nombre} {p.marca} ({p.codigo}): quedan {alerta.stock_al_generar}",
        message=render_to_string("correo/alerta_reorden.txt", contexto),
        html_message=render_to_string("correo/alerta_reorden.html", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=settings.COMPRAS_EMAILS,
        fail_silently=True,
    )
    if enviados:
        AlertaReorden.objects.filter(pk=alerta.pk).update(notificada_en=timezone.now())
