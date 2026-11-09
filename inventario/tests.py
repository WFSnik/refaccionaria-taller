from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import AlertaReorden, Categoria, Marca, Movimiento, Producto, Ubicacion
from .services import StockInsuficiente, registrar_alta, registrar_baja


class Base(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("mostrador", password="clave-de-prueba-123")
        self.cat = Categoria.objects.create(nombre="Filtros de aceite")
        self.marca = Marca.objects.create(nombre="Fram")
        self.a1 = Ubicacion.objects.create(codigo="A-01-1")
        self.a2 = Ubicacion.objects.create(codigo="A-01-2")
        self.filtro = Producto.objects.create(
            codigo="FA-1", nombre="Filtro de aceite", categoria=self.cat, marca=self.marca, punto_reorden=5
        )

    def alta(self, cantidad, ubicacion=None):
        return registrar_alta(
            producto=self.filtro, ubicacion=ubicacion or self.a1, cantidad=cantidad,
            motivo=Movimiento.Motivo.COMPRA, usuario=self.usuario,
        )

    def baja(self, cantidad, ubicacion=None):
        return registrar_baja(
            producto=self.filtro, ubicacion=ubicacion or self.a1, cantidad=cantidad,
            motivo=Movimiento.Motivo.VENTA, usuario=self.usuario,
        )


class FlujoTests(Base):
    def test_alta_suma_por_ubicacion(self):
        self.alta(10)
        self.alta(4, self.a2)
        self.assertEqual(self.filtro.stock_total(), 14)
        self.assertEqual(self.filtro.existencias.get(ubicacion=self.a2).cantidad, 4)

    def test_baja_descuenta_de_la_ubicacion(self):
        self.alta(10)
        mov, alerta = self.baja(3)
        self.assertEqual(mov.stock_resultante, 7)
        self.assertIsNone(alerta)

    def test_llegar_al_punto_de_reorden_genera_alerta_y_notifica(self):
        self.alta(10)
        with self.captureOnCommitCallbacks(execute=True):
            _, alerta = self.baja(5)
        self.assertEqual(alerta.origen, AlertaReorden.Origen.REORDEN)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn("quedan 5", correo.subject)
        self.assertIn("Sugerido pedir: 10", correo.body)
        self.assertIn("/productos/", correo.alternatives[0][0])
        alerta.refresh_from_db()
        self.assertIsNotNone(alerta.notificada_en)

    def test_solo_una_alerta_pendiente_por_producto(self):
        self.alta(10)
        self.baja(6)
        self.baja(1)
        self.assertEqual(AlertaReorden.objects.filter(estado="PENDIENTE").count(), 1)

    def test_baja_sin_stock_no_registra_y_alerta(self):
        self.alta(8)
        with self.assertRaises(StockInsuficiente) as ctx:
            self.baja(12)
        self.assertEqual(self.filtro.stock_total(), 8)
        self.assertEqual(Movimiento.objects.filter(tipo="BAJA").count(), 0)
        self.assertEqual(ctx.exception.alerta.origen, AlertaReorden.Origen.SIN_STOCK)

    def test_falta_solo_en_la_ubicacion_no_alerta(self):
        self.alta(10)
        self.alta(10, self.a2)
        with self.assertRaises(StockInsuficiente) as ctx:
            self.baja(12)
        self.assertIsNone(ctx.exception.alerta)

    def test_reabasto_cierra_alertas(self):
        self.alta(6)
        self.baja(2)
        self.assertTrue(self.filtro.alertas.filter(estado="PENDIENTE").exists())
        self.alta(20)
        self.assertFalse(self.filtro.alertas.filter(estado="PENDIENTE").exists())


class VistasTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_paginas_cargan(self):
        self.alta(10)
        for nombre in ["dashboard", "productos_lista", "movimientos_lista", "movimiento_nuevo", "ubicaciones", "alertas", "producto_crear"]:
            with self.subTest(nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)
        self.assertEqual(self.client.get(reverse("producto_detalle", args=[self.filtro.pk])).status_code, 200)

    def test_vista_previa_del_correo(self):
        self.alta(3)
        alerta = self.filtro.alertas.get()
        r = self.client.get(reverse("alerta_correo", args=[alerta.pk]))
        self.assertContains(r, "Sugerido pedir")

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("dashboard")), "/entrar/?next=/")

    def test_api_busca_por_codigo_de_barras(self):
        self.filtro.codigo_barras = "7501000000011"
        self.filtro.save()
        datos = self.client.get(reverse("api_productos"), {"q": "7501000000011"}).json()
        self.assertEqual(datos["resultados"][0]["codigo"], "FA-1")

    def test_alta_con_producto_nuevo(self):
        r = self.client.post(reverse("movimiento_nuevo"), {
            "tipo": "ALTA", "crear_producto": "1", "ubicacion": self.a1.pk, "cantidad": 12, "motivo": "COMPRA",
            "nuevo-codigo": "FA-2", "nuevo-nombre": "Filtro de aceite", "nuevo-categoria": self.cat.pk,
            "nuevo-marca": self.marca.pk, "nuevo-costo": "50", "nuevo-precio_venta": "90", "nuevo-punto_reorden": "4",
        })
        nuevo = Producto.objects.get(codigo="FA-2")
        self.assertRedirects(r, reverse("producto_detalle", args=[nuevo.pk]))
        self.assertEqual(nuevo.stock_total(), 12)

    def test_producto_nuevo_invalido_no_deja_nada(self):
        self.client.post(reverse("movimiento_nuevo"), {
            "tipo": "ALTA", "crear_producto": "1", "ubicacion": self.a1.pk, "cantidad": 12, "motivo": "COMPRA",
            "nuevo-codigo": "FA-1", "nuevo-nombre": "Duplicado", "nuevo-categoria": self.cat.pk,
            "nuevo-marca": self.marca.pk, "nuevo-costo": "50", "nuevo-precio_venta": "90", "nuevo-punto_reorden": "4",
        })
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_motivo_debe_corresponder_al_tipo(self):
        r = self.client.post(reverse("movimiento_nuevo"), {
            "tipo": "ALTA", "producto": self.filtro.pk, "ubicacion": self.a1.pk, "cantidad": 2, "motivo": "VENTA",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_baja_insuficiente_muestra_error(self):
        self.alta(2)
        r = self.client.post(reverse("movimiento_nuevo"), {
            "tipo": "BAJA", "producto": self.filtro.pk, "ubicacion": self.a1.pk, "cantidad": 5, "motivo": "VENTA",
        })
        self.assertContains(r, "Solo hay 2")
