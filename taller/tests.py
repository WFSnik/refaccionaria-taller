"""Pruebas del flujo completo del diagrama y de las reglas que conectan a los módulos."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from almacen.models import Herramienta, SolicitudPieza
from almacen.services import cancelar_pendiente, entregar_pieza, pedir_faltante, prestar_herramienta
from clientes.models import Cliente, VehiculoCliente
from contabilidad.models import Factura, Gasto
from contabilidad.services import cancelar_factura, emitir_factura, registrar_pago
from inventario.auditorias import abrir_auditoria, cerrar_auditoria
from inventario.models import AlertaReorden, Categoria, Marca, Movimiento, Producto, Ubicacion
from inventario.services import StockInsuficiente, registrar_alta
from mostrador.models import OrdenTrabajo
from mostrador.services import cambiar_estado, emitir_orden, entregar_vehiculo
from proveedores.models import OrdenCompra, Proveedor, SolicitudMaterial
from proveedores.services import (
    cancelar_orden_compra, crear_orden_compra, recibir_material, solicitar_desde_alerta, solicitar_material,
)
from sst.models import Protocolo
from sst.services import entregar_epp, liberar_orden, protocolos_de_orden
from ventas import services as ventas

from .roles import GRUPOS, puede
from .utils import ReglaNegocio

E = OrdenTrabajo.Estado


class Base(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("jefe", password="clave-de-prueba-123")
        self.u = self.admin
        self.a1 = Ubicacion.objects.create(codigo="A-1")
        self.a2 = Ubicacion.objects.create(codigo="A-2")
        cat, marca = Categoria.objects.create(nombre="Filtros"), Marca.objects.create(nombre="Gonher")
        self.filtro = Producto.objects.create(
            codigo="F-1", nombre="Filtro de aceite", categoria=cat, marca=marca,
            costo=Decimal("50.00"), precio_venta=Decimal("100.00"), punto_reorden=2,
        )
        registrar_alta(producto=self.filtro, ubicacion=self.a1, cantidad=10, motivo=Movimiento.Motivo.COMPRA, usuario=self.u)
        self.cliente = Cliente.objects.create(nombre="Cliente Prueba", telefono="3300000000", rfc="xaxx010101000")
        self.vehiculo = VehiculoCliente.objects.create(cliente=self.cliente, marca="Nissan", modelo="Versa", anio=2019, placas="abc-1")
        self.protocolo = Protocolo.objects.create(nombre="Vehículo calzado", requerido_en_orden=True)
        self.proveedor = Proveedor.objects.create(nombre="Proveedor Prueba")

    def orden_presupuestada(self, cantidad=3, mano_obra=Decimal("200.00")):
        orden = emitir_orden(vehiculo=self.vehiculo, sintomas="Ruido", usuario=self.u)
        p = ventas.obtener_presupuesto(orden, self.u)
        p.diagnostico = "Requiere cambio"
        p.save()
        ventas.agregar_refaccion(p, self.filtro, cantidad)
        ventas.agregar_servicio(p, "Mano de obra", 1, mano_obra)
        ventas.enviar_presupuesto(p, self.u)
        return orden, p

    def orden_en_reparacion(self, cantidad=3):
        orden, p = self.orden_presupuestada(cantidad)
        ventas.autorizar(p, self.u, "Cliente Prueba", "PRESENCIAL")
        liberar_orden(orden=orden, confirmados=protocolos_de_orden(), usuario=self.u)
        return orden, orden.solicitudes.get()

    def entregar(self, solicitud, cantidad):
        return entregar_pieza(solicitud=solicitud, ubicacion=self.a1, cantidad=cantidad, recibio="Mecánico", usuario=self.u)


class FlujoCompletoTests(Base):
    def test_del_cliente_a_la_entrega(self):
        orden, s = self.orden_en_reparacion()
        self.entregar(s, 3)
        self.assertEqual(self.filtro.stock_total(), 7)
        mov = Movimiento.objects.filter(referencia=orden.folio).get()
        self.assertEqual((mov.tipo, mov.motivo), ("BAJA", "VENTA"))

        ventas.terminar_orden(orden, self.u)
        factura = emitir_factura(orden, self.u)
        # 3 × 100 + 200 = 500, más 16 % de IVA.
        self.assertEqual((factura.subtotal, factura.iva, factura.total), (Decimal("500.00"), Decimal("80.00"), Decimal("580.00")))
        self.assertEqual(factura.receptor_rfc, "XAXX010101000")

        with self.assertRaisesMessage(ReglaNegocio, "pagada"):
            entregar_vehiculo(orden, self.u)
        registrar_pago(factura=factura, monto=Decimal("80.00"), metodo="EFECTIVO", usuario=self.u)
        factura.refresh_from_db()
        self.assertEqual(factura.estado, Factura.Estado.EMITIDA)
        registrar_pago(factura=factura, monto=Decimal("500.00"), metodo="TARJETA", usuario=self.u)
        entregar_vehiculo(orden, self.u)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.ENTREGADA)
        self.assertEqual(orden.historial.count(), 7)

    def test_no_se_salta_etapas(self):
        orden = emitir_orden(vehiculo=self.vehiculo, sintomas="Ruido", usuario=self.u)
        with self.assertRaises(ReglaNegocio):
            cambiar_estado(orden, E.EN_REPARACION, self.u)
        with self.assertRaises(ReglaNegocio):
            emitir_factura(orden, self.u)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.RECIBIDA)


class VentasTests(Base):
    def test_exige_diagnostico_y_conceptos(self):
        orden = emitir_orden(vehiculo=self.vehiculo, sintomas="x", usuario=self.u)
        p = ventas.obtener_presupuesto(orden, self.u)
        with self.assertRaisesMessage(ReglaNegocio, "diagnóstico"):
            ventas.enviar_presupuesto(p, self.u)
        p.diagnostico = "Algo"
        with self.assertRaisesMessage(ReglaNegocio, "conceptos"):
            ventas.enviar_presupuesto(p, self.u)

    def test_misma_refaccion_suma_en_una_linea(self):
        orden = emitir_orden(vehiculo=self.vehiculo, sintomas="x", usuario=self.u)
        p = ventas.obtener_presupuesto(orden, self.u)
        ventas.agregar_refaccion(p, self.filtro, 2)
        ventas.agregar_refaccion(p, self.filtro, 3)
        self.assertEqual(p.lineas.get().cantidad, 5)

    def test_enviado_no_se_edita_y_autorizar_crea_solicitudes_solo_de_refacciones(self):
        orden, p = self.orden_presupuestada()
        with self.assertRaises(ReglaNegocio):
            ventas.agregar_servicio(p, "Otra", 1, Decimal("1"))
        ventas.autorizar(p, self.u, "Cliente", "TELEFONO")
        self.assertEqual(orden.solicitudes.count(), 1)

    def test_doble_autorizacion_no_duplica(self):
        orden, p = self.orden_presupuestada()
        ventas.autorizar(p, self.u, "Cliente", "TELEFONO")
        with self.assertRaises(ReglaNegocio):
            ventas.autorizar(p, self.u, "Cliente", "TELEFONO")
        self.assertEqual(orden.solicitudes.count(), 1)

    def test_rechazo_cierra_y_no_mueve_stock(self):
        orden, p = self.orden_presupuestada()
        ventas.rechazar(p, self.u, "Cliente", "MENSAJE")
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.RECHAZADA)
        self.assertEqual(self.filtro.stock_total(), 10)

    def test_cancelar_autorizada_cierra_solicitudes(self):
        orden, p = self.orden_presupuestada()
        ventas.autorizar(p, self.u, "Cliente", "TELEFONO")
        ventas.cancelar_orden(orden, self.u)
        self.assertFalse(SolicitudPieza.objects.pendientes().exists())


class AlmacenTests(Base):
    def test_sin_liberacion_de_seguridad_no_sale_pieza(self):
        orden, p = self.orden_presupuestada()
        ventas.autorizar(p, self.u, "Cliente", "TELEFONO")
        with self.assertRaisesMessage(ReglaNegocio, "seguridad"):
            self.entregar(orden.solicitudes.get(), 1)
        self.assertEqual(self.filtro.stock_total(), 10)

    def test_no_entrega_mas_de_lo_solicitado(self):
        _, s = self.orden_en_reparacion(cantidad=2)
        with self.assertRaisesMessage(ReglaNegocio, "Solo faltan"):
            self.entregar(s, 3)

    def test_sin_stock_no_descuenta_pero_conserva_la_alerta(self):
        orden, s = self.orden_en_reparacion(cantidad=20)
        with self.assertRaises(StockInsuficiente):
            self.entregar(s, 15)
        s.refresh_from_db()
        self.assertEqual(s.entregada, 0)
        self.assertEqual(self.filtro.stock_total(), 10)
        self.assertTrue(AlertaReorden.objects.filter(producto=self.filtro, estado="PENDIENTE").exists())

    def test_terminar_exige_piezas_entregadas_y_se_cobra_lo_entregado(self):
        orden, s = self.orden_en_reparacion(cantidad=3)
        self.entregar(s, 1)
        with self.assertRaisesMessage(ReglaNegocio, "sin entregar"):
            ventas.terminar_orden(orden, self.u)
        s.refresh_from_db()
        cancelar_pendiente(s)
        ventas.terminar_orden(orden, self.u)
        factura = emitir_factura(orden, self.u)
        # 1 pieza entregada × 100 + 200 de mano de obra.
        self.assertEqual(factura.subtotal, Decimal("300.00"))

    def test_pedir_faltante_no_duplica(self):
        orden, s = self.orden_en_reparacion(cantidad=15)
        material, creada = pedir_faltante(s, self.u)
        self.assertTrue(creada)
        self.assertEqual((material.cantidad, material.referencia), (5, orden.folio))
        _, creada = pedir_faltante(s, self.u)
        self.assertFalse(creada)

    def test_herramienta_no_se_presta_dos_veces(self):
        h = Herramienta.objects.create(codigo="H", nombre="Gato")
        prestar_herramienta(herramienta=h, mecanico="Ana", usuario=self.u)
        with self.assertRaises(ReglaNegocio):
            prestar_herramienta(herramienta=h, mecanico="Luis", usuario=self.u)


class ProveedoresTests(Base):
    def oc(self, cantidad=10):
        s, _ = solicitar_material(producto=self.filtro, cantidad=cantidad, referencia="OT-1", usuario=self.u)
        return crear_orden_compra(proveedor=self.proveedor, solicitudes=[s], usuario=self.u), s

    def test_recepcion_parcial_y_total_actualiza_stock_y_gastos(self):
        orden, s = self.oc()
        linea = orden.lineas.get()
        recibir_material(orden=orden, cantidades={linea.pk: 4}, ubicacion=self.a2, usuario=self.u)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, OrdenCompra.Estado.PARCIAL)
        self.assertEqual(self.filtro.stock_total(), 14)
        recibir_material(orden=orden, cantidades={linea.pk: 6}, ubicacion=self.a2, usuario=self.u)
        orden.refresh_from_db()
        s.refresh_from_db()
        self.assertEqual(orden.estado, OrdenCompra.Estado.RECIBIDA)
        self.assertEqual(s.estado, SolicitudMaterial.Estado.SURTIDA)
        self.assertEqual(sum(g.monto for g in Gasto.objects.filter(referencia=orden.folio)), Decimal("500.00"))

    def test_no_recibe_de_mas(self):
        orden, _ = self.oc(cantidad=2)
        linea = orden.lineas.get()
        with self.assertRaises(ReglaNegocio):
            recibir_material(orden=orden, cantidades={linea.pk: 3}, ubicacion=self.a2, usuario=self.u)
        self.assertEqual(self.filtro.stock_total(), 10)

    def test_cancelar_regresa_solicitudes(self):
        orden, s = self.oc()
        cancelar_orden_compra(orden)
        s.refresh_from_db()
        self.assertEqual((s.estado, s.orden_compra), (SolicitudMaterial.Estado.PENDIENTE, None))

    def test_alerta_genera_solicitud_con_cantidad_sugerida(self):
        alerta = AlertaReorden.objects.create(producto=self.filtro, origen="REORDEN", stock_al_generar=2, punto_reorden=2)
        solicitud, creada = solicitar_desde_alerta(alerta, self.u)
        self.assertTrue(creada)
        self.assertEqual(solicitud.cantidad, 4)

    def test_dos_solicitudes_del_mismo_producto_van_en_una_linea(self):
        s1, _ = solicitar_material(producto=self.filtro, cantidad=2, referencia="A", usuario=self.u)
        s2, _ = solicitar_material(producto=self.filtro, cantidad=3, referencia="B", usuario=self.u)
        orden = crear_orden_compra(proveedor=self.proveedor, solicitudes=[s1, s2], usuario=self.u)
        self.assertEqual(orden.lineas.get().cantidad, 5)


class ContabilidadTests(Base):
    def factura(self):
        orden, s = self.orden_en_reparacion()
        self.entregar(s, 3)
        ventas.terminar_orden(orden, self.u)
        return orden, emitir_factura(orden, self.u)

    def test_pago_no_excede_saldo(self):
        _, f = self.factura()
        with self.assertRaisesMessage(ReglaNegocio, "excede"):
            registrar_pago(factura=f, monto=f.total + 1, metodo="EFECTIVO", usuario=self.u)

    def test_cancelar_permite_refacturar_salvo_con_pagos(self):
        orden, f = self.factura()
        cancelar_factura(f, self.u)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.TERMINADA)
        f2 = emitir_factura(orden, self.u)
        registrar_pago(factura=f2, monto=Decimal("10"), metodo="EFECTIVO", usuario=self.u)
        with self.assertRaisesMessage(ReglaNegocio, "pagos"):
            cancelar_factura(f2, self.u)

    def test_no_factura_dos_veces(self):
        orden, _ = self.factura()
        with self.assertRaises(ReglaNegocio):
            emitir_factura(orden, self.u)


class SeguridadTests(Base):
    def test_liberar_exige_todos_los_protocolos(self):
        orden, p = self.orden_presupuestada()
        ventas.autorizar(p, self.u, "Cliente", "PRESENCIAL")
        with self.assertRaisesMessage(ReglaNegocio, "Vehículo calzado"):
            liberar_orden(orden=orden, confirmados=[], usuario=self.u)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.AUTORIZADA)

    def test_epp_con_costo_llega_a_contabilidad(self):
        from django.utils import timezone

        entregar_epp(empleado="Ana", equipo="Guantes", cantidad=1, costo_total=Decimal("90"), fecha=timezone.localdate(), usuario=self.u)
        self.assertEqual(Gasto.objects.get().categoria, "SEGURIDAD")


class AuditoriaTests(Base):
    def test_diferencias_generan_ajustes(self):
        a = abrir_auditoria(self.a1, self.u)
        with self.assertRaises(ReglaNegocio):
            abrir_auditoria(self.a1, self.u)
        linea = a.lineas.get()
        self.assertEqual(linea.esperado, 10)
        linea.contado = 8
        linea.save()
        self.assertEqual(cerrar_auditoria(a, self.u), [])
        self.assertEqual(self.filtro.stock_total(), 8)
        self.assertEqual(Movimiento.objects.filter(motivo="AJUSTE", referencia=a.folio).get().tipo, "BAJA")
        with self.assertRaises(ReglaNegocio):
            cerrar_auditoria(a, self.u)

    def test_sin_contar_no_ajusta(self):
        a = abrir_auditoria(self.a1, self.u)
        cerrar_auditoria(a, self.u)
        self.assertEqual(self.filtro.stock_total(), 10)


class RolesYPantallasTests(Base):
    def usuario_con(self, grupo):
        u = get_user_model().objects.create_user(f"u-{grupo}", password="clave-de-prueba-123")
        u.groups.add(Group.objects.get(name=grupo))
        return u

    def test_grupos_creados_por_migracion(self):
        self.assertEqual(set(Group.objects.values_list("name", flat=True)), set(GRUPOS))

    def test_cada_rol_entra_solo_a_su_modulo(self):
        self.client.force_login(self.usuario_con("Almacén"))
        self.assertEqual(self.client.get(reverse("almacen:bandeja")).status_code, 200)
        respuesta = self.client.get(reverse("contabilidad:resumen"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "otra área", status_code=403)
        menu = self.client.get(reverse("taller:flujo"))
        self.assertNotContains(menu, 'href="/contabilidad/"')

    def test_sin_sesion_redirige_al_acceso(self):
        respuesta = self.client.get(reverse("ventas:bandeja"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/entrar/", respuesta["Location"])

    def test_compras_no_ve_datos_de_clientes(self):
        orden = emitir_orden(vehiculo=self.vehiculo, sintomas="x", usuario=self.u)
        self.client.force_login(self.usuario_con("Compras"))
        self.assertEqual(self.client.get(reverse("mostrador:detalle", args=[orden.pk])).status_code, 403)

    def test_flujo_por_pantallas(self):
        c = self.client
        c.force_login(self.admin)
        r = c.post(reverse("mostrador:crear"), {"vehiculo": self.vehiculo.pk, "sintomas": "Ruido", "kilometraje": 1000})
        orden = OrdenTrabajo.objects.get()
        self.assertRedirects(r, reverse("mostrador:detalle", args=[orden.pk]))
        url = reverse("ventas:presupuesto", args=[orden.pk])
        c.post(url, {"accion": "diagnostico", "diagnostico": "Filtro sucio"})
        c.post(url, {"accion": "refaccion", "producto": self.filtro.pk, "cantidad": 2})
        c.post(url, {"accion": "servicio", "descripcion": "Mano de obra", "cantidad": 1, "precio_unitario": "150"})
        self.assertContains(c.get(url), "Filtro de aceite")
        c.post(url, {"accion": "enviar"})
        c.post(url, {"accion": "autorizar", "autorizado_por": "Cliente", "medio": "PRESENCIAL"})
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.AUTORIZADA)
        c.post(reverse("sst:liberar", args=[orden.pk]), {"confirmados": [self.protocolo.pk]})
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.EN_REPARACION)
        s = orden.solicitudes.get()
        c.post(reverse("almacen:entregar", args=[s.pk]), {"ubicacion": self.a1.pk, "cantidad": 2, "recibio": "Mecánico"})
        self.assertEqual(self.filtro.stock_total(), 8)
        c.post(reverse("ventas:terminar", args=[orden.pk]))
        r = c.post(reverse("contabilidad:emitir", args=[orden.pk]))
        factura = Factura.objects.get()
        self.assertRedirects(r, reverse("contabilidad:factura", args=[factura.pk]))
        self.assertEqual(factura.total, Decimal("406.00"))
        c.post(reverse("contabilidad:factura", args=[factura.pk]), {"monto": "406.00", "metodo": "EFECTIVO"})
        c.post(reverse("mostrador:entregar", args=[orden.pk]))
        orden.refresh_from_db()
        self.assertEqual(orden.estado, E.ENTREGADA)

    def test_demo_y_todas_las_pantallas_abren(self):
        VehiculoCliente.objects.all().delete()
        Cliente.objects.all().delete()
        Producto.objects.filter(pk=self.filtro.pk).update(punto_reorden=0)
        for i in range(2, 6):
            p = Producto.objects.create(
                codigo=f"F-{i}", nombre=f"Producto {i}", categoria=self.filtro.categoria, marca=self.filtro.marca,
                costo=Decimal("10"), precio_venta=Decimal("20"), punto_reorden=1,
            )
            registrar_alta(producto=p, ubicacion=self.a1, cantidad=20, motivo=Movimiento.Motivo.COMPRA, usuario=self.u)
        call_command("cargar_demo_taller", usuario=self.admin.username, verbosity=0)
        estados = set(OrdenTrabajo.objects.values_list("estado", flat=True))
        self.assertEqual(estados, {E.RECIBIDA, E.PRESUPUESTADA, E.AUTORIZADA, E.EN_REPARACION, E.FACTURADA, E.ENTREGADA})

        self.client.force_login(self.admin)
        urls = [
            reverse(n) for n in [
                "taller:flujo", "clientes:lista", "clientes:crear", "mostrador:lista", "mostrador:crear", "ventas:bandeja",
                "almacen:bandeja", "almacen:herramientas", "proveedores:bandeja", "proveedores:ordenes",
                "proveedores:proveedores", "proveedores:proveedor_crear", "proveedores:solicitud_manual",
                "contabilidad:resumen", "contabilidad:facturas", "contabilidad:gastos", "contabilidad:gasto_crear",
                "sst:panel", "sst:protocolo_crear", "sst:incidente_crear", "sst:epp_crear", "auditorias", "dashboard",
            ]
        ]
        urls.append(reverse("almacen:existencias") + "?q=producto")
        urls += [reverse("clientes:detalle", args=[c.pk]) for c in Cliente.objects.all()]
        for o in OrdenTrabajo.objects.all():
            urls.append(reverse("mostrador:detalle", args=[o.pk]))
            if hasattr(o, "presupuesto"):
                urls.append(reverse("ventas:presupuesto", args=[o.pk]))
        for f in Factura.objects.all():
            urls += [reverse("contabilidad:factura", args=[f.pk]), reverse("contabilidad:imprimir", args=[f.pk])]
        urls += [reverse("proveedores:orden_detalle", args=[o.pk]) for o in OrdenCompra.objects.all()]
        urls += [reverse("almacen:entregar", args=[s.pk]) for s in SolicitudPieza.objects.pendientes()]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_puede_con_superusuario(self):
        self.assertTrue(puede(self.admin, "contabilidad"))
