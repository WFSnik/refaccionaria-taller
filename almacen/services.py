"""Solicitud y entrega de piezas a las órdenes. Cada entrega es una baja real del inventario."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from inventario.models import Movimiento
from inventario.services import StockInsuficiente, registrar_baja
from mostrador.models import OrdenTrabajo
from proveedores.services import solicitar_material
from taller.utils import ReglaNegocio

from .models import EntregaMaterial, PrestamoHerramienta, SolicitudPieza


def crear_solicitudes(presupuesto):
    """Una solicitud por cada refacción autorizada; la mano de obra no pasa por el almacén."""
    for linea in presupuesto.lineas.filter(producto__isnull=False):
        SolicitudPieza.objects.create(
            orden=presupuesto.orden, linea=linea, producto=linea.producto, cantidad=linea.cantidad
        )


def cancelar_solicitudes(orden):
    orden.solicitudes.pendientes().update(cancelada=True)


def hay_pendientes(orden):
    return orden.solicitudes.pendientes().exists()


def entregado_por_linea(orden):
    return dict(orden.solicitudes.values_list("linea_id", "entregada"))


def entregar_pieza(*, solicitud, ubicacion, cantidad, recibio, usuario):
    fallo = None
    with transaction.atomic():
        orden = OrdenTrabajo.objects.select_for_update().get(pk=solicitud.orden_id)
        if orden.estado != OrdenTrabajo.Estado.EN_REPARACION:
            raise ReglaNegocio(
                f"{orden.folio} está en «{orden.get_estado_display()}»: "
                "las piezas se entregan cuando seguridad libera la orden."
            )
        solicitud = SolicitudPieza.objects.select_for_update().select_related("producto").get(pk=solicitud.pk)
        if cantidad > solicitud.pendiente:
            raise ReglaNegocio(f"Solo faltan {solicitud.pendiente} por entregar.")
        try:
            movimiento, _ = registrar_baja(
                producto=solicitud.producto, ubicacion=ubicacion, cantidad=cantidad,
                motivo=Movimiento.Motivo.VENTA, usuario=usuario, referencia=orden.folio,
                notas=f"Entregado a {recibio}",
            )
        except StockInsuficiente as e:
            # Se relanza al final para no deshacer la alerta de reorden que registrar_baja acaba de crear.
            fallo = e
        else:
            solicitud.entregada += cantidad
            solicitud.save(update_fields=["entregada"])
            return EntregaMaterial.objects.create(
                solicitud=solicitud, movimiento=movimiento, recibio=recibio, usuario=usuario
            )
    raise fallo


def cancelar_pendiente(solicitud):
    if solicitud.orden.estado == OrdenTrabajo.Estado.TERMINADA:
        raise ReglaNegocio("La orden ya está terminada.")
    solicitud.cancelada = True
    solicitud.save(update_fields=["cancelada"])


def pedir_faltante(solicitud, usuario):
    """Almacén → Proveedores: pide lo que falta para surtir la solicitud."""
    faltante = solicitud.pendiente - solicitud.producto.stock_total()
    if faltante <= 0:
        raise ReglaNegocio("Hay stock suficiente: no hace falta pedirlo.")
    return solicitar_material(
        producto=solicitud.producto, cantidad=faltante, referencia=solicitud.orden.folio, usuario=usuario
    )


def prestar_herramienta(*, herramienta, mecanico, usuario, orden=None):
    try:
        with transaction.atomic():
            return PrestamoHerramienta.objects.create(
                herramienta=herramienta, mecanico=mecanico, orden=orden, usuario=usuario
            )
    except IntegrityError:
        raise ReglaNegocio(f"{herramienta.nombre} ya está prestada.") from None


def devolver_herramienta(prestamo):
    prestamo.devuelta = timezone.now()
    prestamo.save(update_fields=["devuelta"])
