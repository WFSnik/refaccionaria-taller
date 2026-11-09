import json
from types import SimpleNamespace
from unittest import mock

from anthropic.types.beta import BetaTextBlock, BetaToolUseBlock
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.models import ConsultaPendiente
from catalogo.tests import Base

from . import bot


USO = SimpleNamespace(input_tokens=10, output_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=3000)


def respuesta(*bloques, stop="end_turn"):
    return SimpleNamespace(content=list(bloques), stop_reason=stop, usage=USO)


def herramienta(nombre, entrada, id_):
    return BetaToolUseBlock(type="tool_use", id=id_, name=nombre, input=entrada)


def texto(t):
    return BetaTextBlock(type="text", text=t)


@mock.patch.object(bot, "con_ia", return_value=False)
class ModoBasicoTests(Base):
    def test_vehiculo_con_anio(self, _):
        r = bot.responder([], "¿Qué filtro de aceite lleva un Versa 2015?")
        self.assertIn("Gonher GP-149", r)
        self.assertIn("Fram PH7317", r)
        self.assertIn("Wix 51356 (por confirmar)", r)
        self.assertIn("lo tenemos: Gonher GP-149", r)

    def test_completa_con_el_vehiculo_anterior(self, _):
        historial = []
        self.assertIn("varias versiones", bot.responder(historial, "versa"))
        self.assertIn("GP-149", bot.responder(historial, "2015"))

    def test_numero_dentro_de_una_frase(self, _):
        r = bot.responder([], "¿El PH7317 tiene equivalente?")
        self.assertIn("Gonher GP-149", r)

    def test_no_encontrado_queda_pendiente(self, _):
        bot.responder([], "tsuru 2012")
        self.assertTrue(ConsultaPendiente.objects.filter(texto="tsuru 2012", canal="ASISTENTE").exists())


@mock.patch.object(bot, "con_ia", return_value=True)
class ClaudeTests(Base):
    def test_usa_las_herramientas_y_devuelve_el_texto(self, _):
        pasos = [
            respuesta(herramienta("buscar_vehiculo", {"texto": "versa 2015"}, "t1"), stop="tool_use"),
            respuesta(herramienta("filtros_del_vehiculo", {"vehiculo_id": self.versa.pk}, "t2"), stop="tool_use"),
            respuesta(texto("Tu Versa lleva el Gonher GP-149 y sí lo tenemos.")),
        ]
        with mock.patch("anthropic.Anthropic") as cliente:
            cliente.return_value.beta.messages.create.side_effect = pasos
            historial = []
            r = bot.responder(historial, "filtro para versa 2015")

        self.assertEqual(r, "Tu Versa lleva el Gonher GP-149 y sí lo tenemos.")
        llamadas = cliente.return_value.beta.messages.create.call_args_list
        self.assertEqual(len(llamadas), 3)
        self.assertNotIn("fallbacks", llamadas[0].kwargs)  # Haiku no tiene respaldo en el servidor
        # Lo que regresa la herramienta es lo que ve el modelo: datos del catálogo, sin ubicaciones ni costos.
        resultado = json.loads(historial[4]["content"][0]["content"])
        aceite = resultado["filtros"][0]["opciones"][0]
        self.assertEqual(aceite["numero_gonher"], "GP-149")
        self.assertEqual(aceite["estado"], "hay")
        self.assertNotIn("ubicacion", json.dumps(resultado))
        self.assertEqual([m["role"] for m in historial], ["user", "assistant", "user", "assistant", "user", "assistant"])

    def test_error_de_herramienta_va_de_regreso_al_modelo(self, _):
        pasos = [
            respuesta(herramienta("filtros_del_vehiculo", {"vehiculo_id": "x"}, "t1"), stop="tool_use"),
            respuesta(texto("Déjame confirmarlo en mostrador.")),
        ]
        with mock.patch("anthropic.Anthropic") as cliente, self.assertLogs("asistente.bot", "ERROR"):
            cliente.return_value.beta.messages.create.side_effect = pasos
            historial = []
            bot.responder(historial, "hola")
        self.assertTrue(historial[2]["content"][0]["is_error"])

    def test_suma_el_gasto_del_dia(self, _):
        cache.clear()
        with mock.patch("anthropic.Anthropic") as cliente:
            cliente.return_value.beta.messages.create.return_value = respuesta(texto("Hola"))
            bot.responder([], "hola")
        # Haiku: 10 × 0.10 + 200 × 0.50 + 3000 × 0.01 = 131 millonésimas de dólar
        self.assertAlmostEqual(bot.gasto_hoy(), 0.000131)

    def test_limite_de_turnos(self, _):
        historial = [{"role": "user", "content": "x"}] * bot.MAX_TURNOS
        self.assertIn("Nueva conversación", bot.responder(historial, "otra"))


class VistaTests(TestCase):
    def test_publica_y_guarda_la_conversacion(self):
        self.assertEqual(self.client.get(reverse("asistente_chat")).status_code, 200)
        with mock.patch.object(bot, "con_ia", return_value=False):
            r = self.client.post(reverse("asistente_mensaje"), json.dumps({"texto": "versa 2015"}),
                                 content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["modo"], "basico")
            pagina = self.client.get(reverse("asistente_chat"))
        self.assertContains(pagina, "versa 2015")

    def test_mensaje_vacio(self):
        r = self.client.post(reverse("asistente_mensaje"), json.dumps({"texto": " "}), content_type="application/json")
        self.assertEqual(r.status_code, 400)


class TopeDiarioTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(ASISTENTE_TOPE_DIARIO_USD=0.5)
    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "prueba"})
    def test_al_llegar_al_tope_pasa_a_modo_basico(self):
        self.assertTrue(bot.con_ia())
        cache.set(bot._llave_gasto(), 600_000)
        self.assertFalse(bot.con_ia())


class LimitesTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(ASISTENTE_LIMITES_IP=[3, 100, 100])
    @mock.patch.object(bot, "con_ia", return_value=False)
    def test_limite_por_minuto(self, _):
        enviar = lambda: self.client.post(reverse("asistente_mensaje"), json.dumps({"texto": "hola"}),
                                          content_type="application/json")
        self.assertEqual([enviar().status_code for _ in range(4)], [200, 200, 200, 429])

    @override_settings(EN_RAILWAY=True)
    def test_ip_real_detras_del_proxy(self):
        from django.test import RequestFactory

        from inventario.seguridad import ip_cliente

        r = RequestFactory().get("/", HTTP_X_REAL_IP="203.0.113.9", HTTP_X_FORWARDED_FOR="203.0.113.9, 84.17.44.1",
                                 REMOTE_ADDR="100.64.0.3")
        self.assertEqual(ip_cliente(r), "203.0.113.9")

    def test_bloquea_intentos_de_contrasena(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user("mostrador", password="clave-de-prueba-123")
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "mostrador", "password": "mala"})
        r = self.client.post(reverse("login"), {"username": "mostrador", "password": "clave-de-prueba-123"})
        self.assertEqual(r.status_code, 200)  # sigue en la página de acceso aunque la clave sea buena
        self.assertContains(r, "Demasiados intentos")
