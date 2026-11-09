"""Seguridad y salud en el trabajo: liberación de órdenes, inspecciones, incidentes y EPP."""

from django.db import transaction
from django.utils import timezone

from contabilidad.gastos import registrar_gasto
from mostrador.models import OrdenTrabajo
from mostrador.services import cambiar_estado
from taller.utils import ReglaNegocio

from .models import EntregaEPP, LiberacionOrden, Protocolo


def protocolos_de_orden():
    return Protocolo.objects.filter(activo=True, requerido_en_orden=True)


@transaction.atomic
def liberar_orden(*, orden, confirmados, usuario, notas=""):
    """Sin esta liberación el almacén no entrega piezas ni empieza la reparación."""
    requeridos = set(protocolos_de_orden())
    faltan = requeridos - set(confirmados)
    if faltan:
        raise ReglaNegocio("Falta confirmar: " + ", ".join(sorted(p.nombre for p in faltan)) + ".")
    cambiar_estado(orden, OrdenTrabajo.Estado.EN_REPARACION, usuario, "Liberada por seguridad")
    liberacion = LiberacionOrden.objects.create(orden=orden, notas=notas, usuario=usuario)
    liberacion.protocolos.set(requeridos)
    return liberacion


@transaction.atomic
def entregar_epp(*, empleado, equipo, cantidad, costo_total, fecha, usuario):
    entrega = EntregaEPP.objects.create(
        empleado=empleado, equipo=equipo, cantidad=cantidad, costo_total=costo_total, fecha=fecha, usuario=usuario
    )
    if costo_total:
        registrar_gasto(
            categoria="SEGURIDAD", concepto=f"EPP: {cantidad} × {equipo} para {empleado}", monto=costo_total,
            referencia=f"EPP-{entrega.pk}", usuario=usuario,
        )
    return entrega


def cerrar_incidente(incidente, accion_correctiva):
    incidente.accion_correctiva = accion_correctiva
    incidente.cerrado = True
    incidente.cerrado_en = timezone.now()
    incidente.save(update_fields=["accion_correctiva", "cerrado", "cerrado_en"])
