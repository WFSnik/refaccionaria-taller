"""Compras: solicitudes de material, órdenes de compra y recepción contra la orden."""

from django.db import transaction

from contabilidad.gastos import registrar_gasto
from inventario.models import Movimiento
from inventario.services import contexto_correo, registrar_alta
from taller.utils import ReglaNegocio

from .models import LineaOrdenCompra, OrdenCompra, SolicitudMaterial

ABIERTAS = [SolicitudMaterial.Estado.PENDIENTE, SolicitudMaterial.Estado.EN_ORDEN]


def solicitar_material(*, producto, cantidad, referencia, usuario):
    """Regresa (solicitud, creada). No duplica una solicitud abierta del mismo producto y referencia."""
    with transaction.atomic():
        abierta = (
            SolicitudMaterial.objects.select_for_update()
            .filter(producto=producto, referencia=referencia, estado__in=ABIERTAS).first()
        )
        if abierta:
            return abierta, False
        return (
            SolicitudMaterial.objects.create(producto=producto, cantidad=cantidad, referencia=referencia, usuario=usuario),
            True,
        )


def solicitar_desde_alerta(alerta, usuario):
    return solicitar_material(
        producto=alerta.producto, cantidad=contexto_correo(alerta)["sugerido"], referencia="Reorden", usuario=usuario
    )


@transaction.atomic
def crear_orden_compra(*, proveedor, solicitudes, usuario):
    ids = [s.pk for s in solicitudes]
    solicitudes = list(
        SolicitudMaterial.objects.select_for_update(of=("self",))
        .filter(pk__in=ids, estado=SolicitudMaterial.Estado.PENDIENTE).select_related("producto")
    )
    if not solicitudes or len(solicitudes) != len(ids):
        raise ReglaNegocio("Alguna solicitud ya no está pendiente; revisa la lista.")
    orden = OrdenCompra.objects.create(proveedor=proveedor, usuario=usuario)
    # Varias solicitudes del mismo producto se piden en una sola línea.
    cantidades = {}
    for s in solicitudes:
        cantidades.setdefault(s.producto_id, [s.producto, 0])[1] += s.cantidad
    LineaOrdenCompra.objects.bulk_create(
        LineaOrdenCompra(orden=orden, producto=p, cantidad=c, costo_unitario=p.costo) for p, c in cantidades.values()
    )
    SolicitudMaterial.objects.filter(pk__in=ids).update(estado=SolicitudMaterial.Estado.EN_ORDEN, orden_compra=orden)
    return orden


@transaction.atomic
def recibir_material(*, orden, cantidades, ubicacion, usuario):
    """Da de alta lo recibido, registra el costo en contabilidad y actualiza la orden. `cantidades` = {línea: n}."""
    orden = OrdenCompra.objects.select_for_update().select_related("proveedor").get(pk=orden.pk)
    if orden.estado not in (OrdenCompra.Estado.ENVIADA, OrdenCompra.Estado.PARCIAL):
        raise ReglaNegocio(f"{orden.folio} ya está {orden.get_estado_display().lower()}.")

    costo = 0
    for linea in orden.lineas.select_for_update(of=("self",)).select_related("producto"):
        n = cantidades.get(linea.pk, 0)
        if not n:
            continue
        if n > linea.pendiente:
            raise ReglaNegocio(f"De {linea.producto.nombre} solo faltan {linea.pendiente} por recibir.")
        registrar_alta(
            producto=linea.producto, ubicacion=ubicacion, cantidad=n, motivo=Movimiento.Motivo.COMPRA,
            usuario=usuario, referencia=orden.folio,
        )
        linea.recibido += n
        linea.save(update_fields=["recibido"])
        costo += n * linea.costo_unitario
    if not any(cantidades.values()):
        raise ReglaNegocio("Captura al menos una cantidad recibida.")

    completa = not any(linea.pendiente for linea in orden.lineas.all())
    orden.estado = OrdenCompra.Estado.RECIBIDA if completa else OrdenCompra.Estado.PARCIAL
    orden.save(update_fields=["estado"])
    if completa:
        orden.solicitudes.update(estado=SolicitudMaterial.Estado.SURTIDA)
    if costo:
        registrar_gasto(
            categoria="COMPRAS", concepto=f"Compra a {orden.proveedor}", monto=costo, referencia=orden.folio, usuario=usuario
        )
    return orden


@transaction.atomic
def cancelar_orden_compra(orden):
    orden = OrdenCompra.objects.select_for_update().get(pk=orden.pk)
    if orden.estado != OrdenCompra.Estado.ENVIADA:
        raise ReglaNegocio("Solo se cancela una orden de la que no se ha recibido nada.")
    orden.estado = OrdenCompra.Estado.CANCELADA
    orden.save(update_fields=["estado"])
    # Lo pedido vuelve a la bandeja para hacerle otra orden.
    orden.solicitudes.update(estado=SolicitudMaterial.Estado.PENDIENTE, orden_compra=None)
