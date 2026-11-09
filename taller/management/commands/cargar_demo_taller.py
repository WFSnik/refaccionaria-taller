"""Datos de ejemplo del taller: personas y empresas inventadas, con órdenes en cada etapa del flujo."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from almacen.models import Herramienta, SolicitudPieza
from almacen.services import entregar_pieza, prestar_herramienta
from clientes.models import Cliente, VehiculoCliente
from contabilidad.models import Gasto
from contabilidad.services import emitir_factura, registrar_pago
from inventario.models import Existencia, Producto
from mostrador.services import emitir_orden, entregar_vehiculo
from proveedores.models import Proveedor
from proveedores.services import crear_orden_compra, recibir_material, solicitar_material
from sst.models import Incidente, Inspeccion, Protocolo
from sst.services import entregar_epp, liberar_orden, protocolos_de_orden
from ventas.services import (
    agregar_refaccion, agregar_servicio, autorizar, enviar_presupuesto, obtener_presupuesto, terminar_orden,
)

CLIENTES = [
    ("Ana Demo Ruiz", "3300000001", "Nissan", "Versa", 2019, "DEMO-001", "Hace ruido al frenar y ya le toca servicio."),
    ("Carlos Ejemplo Mora", "3300000002", "Chevrolet", "Aveo", 2017, "DEMO-002", "Enciende el testigo de aceite."),
    ("Refacciones Prueba SA", "3300000003", "Ford", "Ranger", 2020, "DEMO-003", "Servicio de los 60,000 km."),
    ("Laura Muestra Díaz", "3300000004", "Honda", "CR-V", 2018, "DEMO-004", "Falla al arrancar en frío."),
    ("Jorge Ficticio Soto", "3300000005", "Volkswagen", "Jetta", 2016, "DEMO-005", "Cambio de filtros y aceite."),
    ("Marta Prueba León", "3300000006", "Toyota", "Corolla", 2021, "DEMO-006", "Vibración en el volante."),
]

PROTOCOLOS = [
    ("Vehículo inmovilizado y calzado", "Freno de mano, calzas y llave retirada antes de iniciar.", "", 0, True),
    ("Equipo de protección del mecánico", "Guantes, lentes y calzado de seguridad.", "NOM-017-STPS", 0, True),
    ("Extintores vigentes", "Carga vigente y acceso libre.", "NOM-002-STPS", 30, False),
    ("Manejo de aceites y sustancias", "Almacenamiento, etiquetado y derrames.", "NOM-005-STPS", 30, False),
    ("Revisión de elevadores y gatos", "Estado de los equipos de izaje.", "NOM-004-STPS", 90, False),
]


class Command(BaseCommand):
    help = "Carga clientes, proveedores, protocolos y órdenes de ejemplo. No hace nada si ya hay clientes."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", required=True, help="Usuario que queda como autor de los registros")

    @transaction.atomic
    def handle(self, *args, **opts):
        if Cliente.objects.exists():
            self.stdout.write("Ya hay clientes: no se cargó el ejemplo del taller.")
            return
        try:
            self.u = get_user_model().objects.get(username=opts["usuario"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"No existe el usuario {opts['usuario']}") from None

        if not Producto.objects.exists():
            call_command("cargar_demo", usuario=self.u.username, stdout=self.stdout)
        self.productos = list(
            Producto.objects.filter(activo=True).con_stock().filter(stock__gt=F("punto_reorden") + 3).order_by("codigo")
        )
        if len(self.productos) < 4:
            raise CommandError("Se necesitan al menos 4 productos con stock para el ejemplo.")

        self.base()
        vehiculos = self.clientes()
        self.ordenes(vehiculos)
        self.compras()
        self.stdout.write(self.style.SUCCESS("Ejemplo del taller cargado."))

    def base(self):
        for nombre, descripcion, norma, frecuencia, en_orden in PROTOCOLOS:
            p = Protocolo.objects.create(
                nombre=nombre, descripcion=descripcion, norma=norma, frecuencia_dias=frecuencia, requerido_en_orden=en_orden
            )
            if frecuencia and norma != "NOM-004-STPS":
                Inspeccion.objects.create(protocolo=p, resultado="CUMPLE", usuario=self.u)
        Incidente.objects.create(
            tipo="RIESGO", severidad="MEDIA", area="Bahía 2", reportado_por=self.u,
            descripcion="Derrame de aceite sin señalizar junto al elevador.",
        )
        entregar_epp(
            empleado="Mecánico Demo", equipo="Guantes de nitrilo", cantidad=2, costo_total=Decimal("180.00"),
            fecha=Gasto._meta.get_field("fecha").default(), usuario=self.u,
        )
        for codigo, nombre, ubicacion in [
            ("H-001", "Gato hidráulico", "Bahía 1"),
            ("H-002", "Juego de dados", "Tablero A"),
            ("H-003", "Escáner OBD-II", "Oficina"),
        ]:
            Herramienta.objects.create(codigo=codigo, nombre=nombre, ubicacion=ubicacion)
        Proveedor.objects.create(
            nombre="Distribuidora Demo del Bajío", contacto="Compras Demo", telefono="3300001000", dias_entrega=2
        )
        Proveedor.objects.create(nombre="Lubricantes Ejemplo", contacto="Ventas Ejemplo", telefono="3300002000", dias_entrega=5)

    def clientes(self):
        vehiculos = []
        for nombre, telefono, marca, modelo, anio, placas, sintomas in CLIENTES:
            cliente = Cliente.objects.create(nombre=nombre, telefono=telefono)
            v = VehiculoCliente.objects.create(cliente=cliente, marca=marca, modelo=modelo, anio=anio, placas=placas)
            vehiculos.append((v, sintomas))
        return vehiculos

    def presupuesto(self, vehiculo, sintomas, productos):
        orden = emitir_orden(vehiculo=vehiculo, sintomas=sintomas, kilometraje=85000, usuario=self.u)
        p = obtener_presupuesto(orden, self.u)
        p.diagnostico = "Revisión visual y prueba de manejo: se confirma lo reportado por el cliente."
        p.save(update_fields=["diagnostico"])
        for producto in productos:
            agregar_refaccion(p, producto, 1)
        agregar_servicio(p, "Mano de obra", 1, Decimal("450.00"))
        return orden, p

    def entregar_todo(self, orden):
        for s in SolicitudPieza.objects.pendientes().filter(orden=orden):
            existencia = Existencia.objects.filter(producto=s.producto, cantidad__gte=s.pendiente).first()
            entregar_pieza(
                solicitud=s, ubicacion=existencia.ubicacion, cantidad=s.pendiente, recibio="Mecánico Demo", usuario=self.u
            )

    def avanzar(self, vehiculo, sintomas, productos, hasta):
        orden, p = self.presupuesto(vehiculo, sintomas, productos)
        pasos = ["enviado", "autorizado", "liberado", "terminado", "facturado", "entregado"]
        hasta = pasos.index(hasta)
        enviar_presupuesto(p, self.u)
        if hasta >= 1:
            autorizar(p, self.u, vehiculo.cliente.nombre, "PRESENCIAL")
        if hasta >= 2:
            liberar_orden(orden=orden, confirmados=protocolos_de_orden(), usuario=self.u)
        if hasta >= 3:
            self.entregar_todo(orden)
            terminar_orden(orden, self.u)
        if hasta >= 4:
            orden.refresh_from_db()
            factura = emitir_factura(orden, self.u)
        if hasta >= 5:
            registrar_pago(factura=factura, monto=factura.total, metodo="TARJETA", usuario=self.u)
            entregar_vehiculo(orden, self.u)
        return orden

    def ordenes(self, vehiculos):
        a, b, c, d = self.productos[:4]
        # Una orden por etapa, de la recién recibida a la ya entregada.
        emitir_orden(vehiculo=vehiculos[0][0], sintomas=vehiculos[0][1], kilometraje=64000, usuario=self.u)
        self.avanzar(*vehiculos[1], [a], "enviado")
        self.avanzar(*vehiculos[2], [a, b], "autorizado")
        en_taller = self.avanzar(*vehiculos[3], [b, c], "liberado")
        prestar_herramienta(herramienta=Herramienta.objects.get(codigo="H-003"), mecanico="Mecánico Demo", orden=en_taller, usuario=self.u)
        self.avanzar(*vehiculos[4], [c], "facturado")
        self.avanzar(*vehiculos[5], [d], "entregado")

    def compras(self):
        ubicacion = Existencia.objects.first().ubicacion
        s1, _ = solicitar_material(producto=self.productos[0], cantidad=6, referencia="Reorden", usuario=self.u)
        s2, _ = solicitar_material(producto=self.productos[1], cantidad=4, referencia="Reorden", usuario=self.u)
        orden = crear_orden_compra(proveedor=Proveedor.objects.first(), solicitudes=[s1, s2], usuario=self.u)
        primera = orden.lineas.first()
        recibir_material(orden=orden, cantidades={primera.pk: primera.cantidad}, ubicacion=ubicacion, usuario=self.u)
        solicitar_material(producto=self.productos[2], cantidad=5, referencia="Reorden", usuario=self.u)
