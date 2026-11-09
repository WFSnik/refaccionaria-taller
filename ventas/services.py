"""Diagnóstico, presupuesto y autorización. Autorizar genera las solicitudes de piezas al almacén."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from almacen.services import cancelar_solicitudes, crear_solicitudes, entregado_por_linea, hay_pendientes
from mostrador.models import OrdenTrabajo
from mostrador.services import cambiar_estado
from taller.utils import ReglaNegocio

from .models import LineaPresupuesto, Presupuesto

E = OrdenTrabajo.Estado


def obtener_presupuesto(orden, usuario):
    presupuesto, _ = Presupuesto.objects.get_or_create(orden=orden, defaults={"creado_por": usuario})
    return presupuesto


def _exigir_editable(presupuesto):
    if not presupuesto.editable:
        raise ReglaNegocio("El presupuesto ya se envió: regrésalo a edición para cambiarlo.")


@transaction.atomic
def agregar_refaccion(presupuesto, producto, cantidad):
    _exigir_editable(presupuesto)
    linea = presupuesto.lineas.filter(producto=producto).first()
    if linea:
        LineaPresupuesto.objects.filter(pk=linea.pk).update(cantidad=F("cantidad") + cantidad)
        return
    presupuesto.lineas.create(
        producto=producto, descripcion=producto.nombre, cantidad=cantidad, precio_unitario=producto.precio_venta
    )


def agregar_servicio(presupuesto, descripcion, cantidad, precio_unitario):
    _exigir_editable(presupuesto)
    return presupuesto.lineas.create(descripcion=descripcion, cantidad=cantidad, precio_unitario=precio_unitario)


def quitar_linea(linea):
    _exigir_editable(linea.presupuesto)
    linea.delete()


@transaction.atomic
def enviar_presupuesto(presupuesto, usuario):
    if not presupuesto.diagnostico.strip():
        raise ReglaNegocio("Captura el diagnóstico antes de enviar el presupuesto.")
    if not presupuesto.lineas.exists():
        raise ReglaNegocio("El presupuesto no tiene conceptos.")
    cambiar_estado(presupuesto.orden, E.PRESUPUESTADA, usuario, f"Total ${presupuesto.montos()['total']:,.2f}")


def regresar_a_edicion(presupuesto, usuario):
    cambiar_estado(presupuesto.orden, E.RECIBIDA, usuario, "Presupuesto regresado a edición")


@transaction.atomic
def autorizar(presupuesto, usuario, autorizado_por, medio):
    cambiar_estado(presupuesto.orden, E.AUTORIZADA, usuario, f"Autorizó {autorizado_por}")
    presupuesto.autorizado_por = autorizado_por
    presupuesto.medio = medio
    presupuesto.decidido_en = timezone.now()
    presupuesto.save(update_fields=["autorizado_por", "medio", "decidido_en"])
    crear_solicitudes(presupuesto)


@transaction.atomic
def rechazar(presupuesto, usuario, autorizado_por, medio):
    cambiar_estado(presupuesto.orden, E.RECHAZADA, usuario, f"Rechazó {autorizado_por}")
    presupuesto.autorizado_por = autorizado_por
    presupuesto.medio = medio
    presupuesto.decidido_en = timezone.now()
    presupuesto.save(update_fields=["autorizado_por", "medio", "decidido_en"])


@transaction.atomic
def cancelar_orden(orden, usuario, nota="Orden cancelada"):
    cambiar_estado(orden, E.CANCELADA, usuario, nota)
    cancelar_solicitudes(orden)


@transaction.atomic
def terminar_orden(orden, usuario):
    if hay_pendientes(orden):
        raise ReglaNegocio("Hay piezas sin entregar: el almacén debe entregarlas o cancelar lo que ya no se ocupó.")
    cambiar_estado(orden, E.TERMINADA, usuario, "Reparación terminada")


def lineas_a_facturar(orden):
    """Conceptos reales de la orden: en refacciones se cobra lo que el almacén sí entregó."""
    entregado = entregado_por_linea(orden)
    conceptos = []
    for linea in orden.presupuesto.lineas.all():
        cantidad = entregado.get(linea.pk, 0) if linea.producto_id else linea.cantidad
        if cantidad:
            conceptos.append(
                {"descripcion": linea.descripcion, "cantidad": cantidad, "precio_unitario": linea.precio_unitario}
            )
    return conceptos
