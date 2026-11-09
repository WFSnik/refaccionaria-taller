"""Emisión de órdenes de trabajo y sus cambios de estado. Los demás módulos avanzan la orden por aquí."""

from django.db import transaction

from taller.utils import ReglaNegocio

from .models import HistorialOrden, OrdenTrabajo

E = OrdenTrabajo.Estado

TRANSICIONES = {
    E.RECIBIDA: {E.PRESUPUESTADA, E.CANCELADA},
    E.PRESUPUESTADA: {E.RECIBIDA, E.AUTORIZADA, E.RECHAZADA, E.CANCELADA},
    E.AUTORIZADA: {E.EN_REPARACION, E.CANCELADA},
    E.EN_REPARACION: {E.TERMINADA},
    E.TERMINADA: {E.FACTURADA},
    E.FACTURADA: {E.ENTREGADA, E.TERMINADA},  # Regresa a terminada si se cancela la factura.
    E.ENTREGADA: set(),
    E.RECHAZADA: set(),
    E.CANCELADA: set(),
}


@transaction.atomic
def emitir_orden(*, vehiculo, sintomas, usuario, kilometraje=None):
    orden = OrdenTrabajo.objects.create(
        vehiculo=vehiculo, sintomas=sintomas, kilometraje=kilometraje, creada_por=usuario
    )
    HistorialOrden.objects.create(orden=orden, estado=orden.estado, nota="Orden emitida en mostrador", usuario=usuario)
    return orden


@transaction.atomic
def cambiar_estado(orden, nuevo, usuario, nota=""):
    """Bloquea la orden para que dos personas no la avancen a la vez y valida que el paso exista."""
    orden_bd = OrdenTrabajo.objects.select_for_update().get(pk=orden.pk)
    if nuevo not in TRANSICIONES[orden_bd.estado]:
        raise ReglaNegocio(
            f"{orden_bd.folio} está en «{orden_bd.get_estado_display()}» y no puede pasar a «{E(nuevo).label}»."
        )
    orden_bd.estado = nuevo
    orden_bd.save(update_fields=["estado", "actualizada"])
    orden.estado = nuevo
    HistorialOrden.objects.create(orden=orden_bd, estado=nuevo, nota=nota, usuario=usuario)
    return orden


def entregar_vehiculo(orden, usuario):
    if not orden.facturas.filter(estado="PAGADA").exists():
        raise ReglaNegocio("El vehículo se entrega hasta que la factura esté pagada.")
    return cambiar_estado(orden, E.ENTREGADA, usuario, "Vehículo entregado al cliente")
