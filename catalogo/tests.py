from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from inventario.models import Categoria, Marca, Movimiento, Producto, Ubicacion
from inventario.services import registrar_alta

from .models import Aplicacion, ConsultaPendiente, Equivalencia, TipoPieza, Vehiculo
from .services import buscar_numero, buscar_vehiculos, interpretar, piezas_para


class Base(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("mostrador", password="clave-de-prueba-123")
        self.versa = Vehiculo.objects.create(marca="Nissan", modelo="VERSA", anio_inicio=2012, anio_fin=2019, motor="L4-1.6L")
        Vehiculo.objects.create(marca="Nissan", modelo="VERSA", anio_inicio=2020, anio_fin=2025, motor="L4-1.6L")
        Vehiculo.objects.create(marca="Honda", modelo="CR-V", anio_inicio=2017, anio_fin=2022, motor="L4-1.5L Turbo")
        Aplicacion.objects.create(vehiculo=self.versa, tipo=TipoPieza.ACEITE, numero_gonher="GP-149")
        Aplicacion.objects.create(vehiculo=self.versa, tipo=TipoPieza.AIRE, numero_gonher="GA-306")
        Equivalencia.objects.create(numero_gonher="GP-149", marca="Fram", numero="PH7317",
                                    confianza=Equivalencia.Confianza.FABRICANTE, fuente="catálogo")
        Equivalencia.objects.create(numero_gonher="GP-149", marca="Wix", numero="51356",
                                    confianza=Equivalencia.Confianza.UNA_FUENTE, fuente="web")
        cat = Categoria.objects.create(nombre="Filtros de aceite")
        self.ubic = Ubicacion.objects.create(codigo="B-01-1")
        self.gonher = Producto.objects.create(codigo="FA-1", nombre="Filtro", categoria=cat,
                                              marca=Marca.objects.create(nombre="Gonher"), numero_parte="gp-149 ")
        self.fram = Producto.objects.create(codigo="FA-2", nombre="Filtro", categoria=cat,
                                            marca=Marca.objects.create(nombre="Fram"), numero_parte="PH7317")
        registrar_alta(producto=self.gonher, ubicacion=self.ubic, cantidad=5,
                       motivo=Movimiento.Motivo.COMPRA, usuario=self.usuario)


class BusquedaTests(Base):
    def test_interpreta_lo_que_escribe_la_gente(self):
        self.assertEqual(interpretar("¿Qué filtro de aceite lleva mi Versa 2015 1.6?"), (2015, "1.6", ["versa"]))

    def test_busca_por_modelo_y_anio(self):
        self.assertEqual(list(buscar_vehiculos("versa 2015")), [self.versa])
        self.assertEqual(buscar_vehiculos("nissan versa").count(), 2)
        self.assertFalse(buscar_vehiculos("versa 2030").exists())

    def test_modelo_sin_guion(self):
        self.assertEqual(buscar_vehiculos("crv 2018").count(), 1)

    def test_piezas_con_equivalencias_y_existencias(self):
        grupos = piezas_para(self.versa)
        self.assertEqual([g["tipo"] for g in grupos], [TipoPieza.ACEITE, TipoPieza.AIRE])
        aceite = grupos[0]["opciones"][0]
        self.assertEqual(aceite["numero_gonher"], "GP-149")
        self.assertEqual({p.codigo for p in aceite["productos"]}, {"FA-1", "FA-2"})
        self.assertTrue(aceite["disponible"])
        aire = grupos[1]["opciones"][0]
        self.assertEqual((aire["productos"], aire["disponible"]), ([], False))

    def test_numero_de_otra_marca_llega_a_su_grupo_gonher(self):
        for escrito in ("ph-7317", "PH7317", "gp149", "51356"):
            r = buscar_numero(escrito)
            self.assertEqual([g["numero_gonher"] for g in r["grupos"]], ["GP-149"], escrito)
        self.assertIsNone(buscar_numero("ZZ-99999"))

    def test_equivalencia_de_una_fuente_queda_por_confirmar(self):
        self.assertFalse(Equivalencia.objects.get(marca="Wix").confirmada)
        self.assertTrue(Equivalencia.objects.get(marca="Fram").confirmada)


class VistasTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_un_resultado_muestra_las_piezas(self):
        r = self.client.get(reverse("catalogo_vehiculos"), {"q": "versa 2015"})
        self.assertContains(r, "GP-149")
        self.assertContains(r, "PH7317")
        self.assertContains(r, "por confirmar")

    def test_varias_versiones_pide_elegir(self):
        r = self.client.get(reverse("catalogo_vehiculos"), {"q": "versa"})
        self.assertContains(r, "Hay 2 versiones")

    def test_lo_que_no_encuentra_queda_pendiente(self):
        self.client.get(reverse("catalogo_vehiculos"), {"q": "tsuru 2012"})
        self.client.get(reverse("catalogo_numero"), {"n": "XX-1"})
        self.assertEqual(
            sorted(ConsultaPendiente.objects.values_list("texto", flat=True)), ["Número XX-1", "tsuru 2012"]
        )

    def test_selectores_encadenados(self):
        r = self.client.get(reverse("catalogo_opciones"), {"marca": "Nissan", "modelo": "VERSA"})
        self.assertEqual(r.json()["modelos"], ["VERSA"])
        self.assertEqual(r.json()["anios"][0], 2025)
        self.assertEqual(len(r.json()["anios"]), 14)

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("catalogo_vehiculos")).status_code, 302)


class CargaTests(TestCase):
    def test_carga_los_csv_del_catalogo(self):
        call_command("cargar_catalogo", stdout=StringIO())
        self.assertEqual(Vehiculo.objects.count(), 3)  # muestra incluida en el repo público
        versa = Vehiculo.objects.get(marca="Nissan", modelo="VERSA", anio_inicio=2012, anio_fin=2019)
        self.assertEqual(
            sorted(versa.aplicaciones.values_list("numero_gonher", flat=True)),
            ["GA-306", "GAC-2271", "GAF-2271", "GP-149", "GPS-149"],
        )
        self.assertTrue(Equivalencia.objects.filter(numero_gonher="GP-149", marca="Wix", numero="51356").exists())
