"""Facturación y cobro de las órdenes de trabajo."""

from django.db import transaction

from mostrador.models import OrdenTrabajo
from mostrador.services import cambiar_estado
from taller.utils import ReglaNegocio, totales
from ventas.services import lineas_a_facturar

from .models import Factura, LineaFactura, Pago

E = OrdenTrabajo.Estado


@transaction.atomic
def emitir_factura(orden, usuario):
    # cambiar_estado bloquea la orden y solo deja facturar una terminada, así no se factura dos veces.
    cambiar_estado(orden, E.FACTURADA, usuario, "Factura emitida")
    conceptos = lineas_a_facturar(orden)
    subtotal, iva, total = totales(sum(c["cantidad"] * c["precio_unitario"] for c in conceptos))
    cliente = orden.cliente
    factura = Factura.objects.create(
        orden=orden, receptor_nombre=cliente.nombre, receptor_rfc=cliente.rfc,
        subtotal=subtotal, iva=iva, total=total, usuario=usuario,
        # Sin nada que cobrar (todo se canceló) queda saldada desde el inicio.
        estado=Factura.Estado.EMITIDA if total else Factura.Estado.PAGADA,
    )
    LineaFactura.objects.bulk_create(LineaFactura(factura=factura, **c) for c in conceptos)
    return factura


@transaction.atomic
def registrar_pago(*, factura, monto, metodo, usuario, referencia=""):
    factura = Factura.objects.select_for_update().get(pk=factura.pk)
    if factura.estado != Factura.Estado.EMITIDA:
        raise ReglaNegocio(f"La factura {factura.folio} está {factura.get_estado_display().lower()}.")
    if monto <= 0:
        raise ReglaNegocio("El pago debe ser mayor a cero.")
    if monto > factura.saldo:
        raise ReglaNegocio(f"El pago excede el saldo de ${factura.saldo:,.2f}.")
    pago = Pago.objects.create(factura=factura, monto=monto, metodo=metodo, referencia=referencia, usuario=usuario)
    if factura.saldo == 0:
        factura.estado = Factura.Estado.PAGADA
        factura.save(update_fields=["estado"])
    return pago


@transaction.atomic
def cancelar_factura(factura, usuario):
    factura = Factura.objects.select_for_update().select_related("orden").get(pk=factura.pk)
    if factura.estado == Factura.Estado.CANCELADA:
        raise ReglaNegocio("La factura ya estaba cancelada.")
    if factura.pagos.exists():
        raise ReglaNegocio("La factura tiene pagos registrados y no se puede cancelar.")
    factura.estado = Factura.Estado.CANCELADA
    factura.save(update_fields=["estado"])
    cambiar_estado(factura.orden, E.TERMINADA, usuario, f"Factura {factura.folio} cancelada")
