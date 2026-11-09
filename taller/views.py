from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from almacen.models import SolicitudPieza
from clientes.models import Cliente
from contabilidad.models import Factura
from inventario.models import AlertaReorden, Auditoria
from mostrador.models import OrdenTrabajo
from proveedores.models import OrdenCompra, SolicitudMaterial
from sst.models import Incidente

from .roles import puede

E = OrdenTrabajo.Estado


@login_required
def flujo(request):
    """Mapa del taller: cada módulo del diagrama con lo que tiene pendiente en este momento."""
    ordenes = OrdenTrabajo.objects.all()
    modulos = [
        {
            "nombre": "Cliente", "sub": "Vehículo", "icono": "i-usuarios", "url": "clientes:lista", "permiso": "clientes",
            "funciones": ["Registro de clientes", "Vehículos por cliente", "Historial de órdenes"],
            "dato": Cliente.objects.count(), "etiqueta": "clientes", "siguiente": "Entrega su vehículo a mostrador",
        },
        {
            "nombre": "Mostrador", "sub": "Recepción y atención", "icono": "i-recepcion", "url": "mostrador:lista", "permiso": "ordenes",
            "funciones": ["Registro de cliente", "Vehículo y síntomas", "Emisión de orden de trabajo"],
            "dato": ordenes.filter(estado__in=OrdenTrabajo.ABIERTOS).count(), "etiqueta": "órdenes abiertas",
            "siguiente": "Pasa la orden a ventas",
        },
        {
            "nombre": "Ventas", "sub": "Presupuestos y servicios", "icono": "i-presupuesto", "url": "ventas:bandeja", "permiso": "ventas",
            "funciones": ["Diagnóstico inicial", "Presupuesto", "Autorización de reparación"],
            "dato": ordenes.filter(estado__in=[E.RECIBIDA, E.PRESUPUESTADA]).count(), "etiqueta": "por diagnosticar o autorizar",
            "siguiente": "Pide piezas al almacén y registra la venta",
        },
        {
            "nombre": "Seguridad", "sub": "SST: salud y seguridad en el trabajo", "icono": "i-escudo", "url": "sst:panel", "permiso": "sst",
            "funciones": ["Monitoreo de protocolos", "Prevención de riesgos", "Protección de empleados y equipos"],
            "dato": ordenes.filter(estado=E.AUTORIZADA).count() + Incidente.objects.filter(cerrado=False).count(),
            "etiqueta": "por liberar o reportes abiertos", "siguiente": "Libera las órdenes antes de la reparación",
        },
        {
            "nombre": "Almacén", "sub": "Refacciones y herramientas", "icono": "i-almacen", "url": "almacen:bandeja", "permiso": "almacen",
            "funciones": ["Consulta de existencia", "Solicitud de piezas", "Entrega de materiales para trabajo"],
            "dato": SolicitudPieza.objects.pendientes().count(), "etiqueta": "piezas por entregar",
            "siguiente": "Descuenta del inventario; pide lo que falta",
        },
        {
            "nombre": "Inventario", "sub": "Control de existencias", "icono": "i-caja", "url": "dashboard", "permiso": None,
            "funciones": ["Gestión de stock", "Auditorías de inventario", "Control de entradas y salidas"],
            "dato": AlertaReorden.objects.filter(estado=AlertaReorden.Estado.PENDIENTE).count()
            + Auditoria.objects.filter(abierta=True).count(),
            "etiqueta": "alertas o auditorías abiertas", "siguiente": "Avisa a compras al llegar al punto de reorden",
        },
        {
            "nombre": "Proveedores", "sub": "Abastecimiento", "icono": "i-camion", "url": "proveedores:bandeja", "permiso": "proveedores",
            "funciones": ["Compra de refacciones", "Suministro de materiales", "Recepción contra orden de compra"],
            "dato": SolicitudMaterial.objects.filter(estado=SolicitudMaterial.Estado.PENDIENTE).count()
            + OrdenCompra.objects.filter(estado__in=[OrdenCompra.Estado.ENVIADA, OrdenCompra.Estado.PARCIAL]).count(),
            "etiqueta": "solicitudes u órdenes abiertas", "siguiente": "Surte el inventario y registra el costo",
        },
        {
            "nombre": "Contabilidad", "sub": "Facturación y pagos", "icono": "i-factura", "url": "contabilidad:resumen", "permiso": "contabilidad",
            "funciones": ["Emisión de facturas", "Cobro a clientes", "Registro de costos operacionales"],
            "dato": ordenes.filter(estado=E.TERMINADA).count() + Factura.objects.filter(estado=Factura.Estado.EMITIDA).count(),
            "etiqueta": "por facturar o cobrar", "siguiente": "Con el pago, mostrador entrega el vehículo",
        },
    ]
    for m in modulos:
        m["permitido"] = m["permiso"] is None or puede(request.user, m["permiso"])
    return render(request, "taller/flujo.html", {"modulos": modulos})
