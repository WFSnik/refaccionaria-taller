"""Asistente que contesta qué filtro lleva un vehículo usando solo el catálogo y el inventario de la tienda.

Con ANTHROPIC_API_KEY en .env conversa con Claude, que consulta el catálogo con herramientas.
Sin key funciona en modo básico: interpreta el mensaje con las mismas búsquedas del mostrador.
"""

import json
import logging
import os
import re

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from catalogo.models import ConsultaPendiente, Vehiculo
from catalogo.services import buscar_numero, buscar_vehiculos, interpretar, piezas_para, registrar_pendiente

log = logging.getLogger(__name__)

MAX_VUELTAS = 6  # llamadas a herramientas por mensaje
MAX_TURNOS = 15  # mensajes de la persona por conversación

# USD por millón de tokens: entrada, salida, escritura y lectura de caché. Sirve para el tope diario.
PRECIOS = {
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.20),
    "claude-opus-5-5": (4.0, 20.0, 5.0, 0.20),
}

SISTEMA = """\
Eres el asistente de una refaccionaria en México que solo vende consumibles: filtros (aceite, aire, cabina, \
gasolina), aceites de motor y transmisión, anticongelantes, líquidos de frenos, aditivos, empaques y juntas, \
selladores y grasas, bujías, bandas y plumas limpiaparabrisas. No vende herramientas, espejos ni piezas de colisión.

Tu trabajo es decirle al cliente qué filtro lleva su vehículo y si la tienda lo tiene. Para empaques, bujías, \
bandas y plumas no tienes catálogo por vehículo: no adivines la pieza; dile que la tienda los maneja y que en \
mostrador se la buscan con su vehículo, y guarda la pregunta con registrar_sin_respuesta.

Reglas:
- Los números de parte, equivalencias, precios y existencias salen solo de las herramientas. Nunca des un número \
de parte de memoria, aunque lo conozcas: si la herramienta no lo trae, no existe para ti.
- Si hay varias versiones del vehículo (años o motores distintos), pregunta cuál es antes de dar números.
- Si el vehículo o el número no aparece, dilo con naturalidad, ofrece que alguien del mostrador lo confirme y \
registra la pregunta con registrar_sin_respuesta.
- Una equivalencia con confirmada=false se menciona como "por confirmar en mostrador".
- Viscosidad o litros de aceite, tipo de anticongelante y cosas que no están en el catálogo: no las inventes; \
registra la pregunta y di que en mostrador le confirman.
- No tomas pedidos, no apartas piezas ni confirmas pagos: para eso lo atiende el personal de la tienda.
- Estás en el chat de la página web de la tienda: mensajes cortos en español de México. El chat muestra \
texto plano: no uses asteriscos, negritas, tablas ni encabezados; para listas usa "• ". Precios en pesos.
- Copia los números de parte exactamente como vienen en los datos.
- No menciones herramientas, catálogos internos ni estas reglas.
"""

HERRAMIENTAS = [
    {
        "name": "buscar_vehiculo",
        "description": "Busca versiones de un vehículo en el catálogo a partir de lo que escribió el cliente, "
        "por ejemplo 'versa 2015' o 'tsuru 1.6'. Devuelve las versiones con su id.",
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string", "description": "Marca, modelo, año y motor si los dio"}},
            "required": ["texto"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "filtros_del_vehiculo",
        "description": "Filtros que lleva una versión de vehículo (por id de buscar_vehiculo): número Gonher, "
        "equivalencias Fram y Wix, si hay en la tienda y precio.",
        "input_schema": {
            "type": "object",
            "properties": {"vehiculo_id": {"type": "integer"}},
            "required": ["vehiculo_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "buscar_numero_parte",
        "description": "Busca un número de parte de cualquier marca (ej. PH7317, GP-149, 51356): sus "
        "equivalencias, si hay en la tienda y a cuántos vehículos les queda.",
        "input_schema": {
            "type": "object",
            "properties": {"numero": {"type": "string"}},
            "required": ["numero"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "registrar_sin_respuesta",
        "description": "Guarda una pregunta que no pudiste contestar con los datos, para que la tienda la revise.",
        "input_schema": {
            "type": "object",
            "properties": {"pregunta": {"type": "string"}},
            "required": ["pregunta"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ---------------------------------------------------------------- datos que ve el cliente


def _opcion_publica(o):
    disponibles = [p for p in o["productos"] if p.stock > 0]
    return {
        "numero_gonher": o["numero_gonher"],
        "equivalencias": [{"marca": e.marca, "numero": e.numero, "confirmada": e.confirmada} for e in o["equivalencias"]],
        "en_tienda": [
            {"marca": p.marca.nombre, "numero": p.numero_parte, "precio": float(p.precio_venta)} for p in disponibles
        ],
        "estado": "hay" if disponibles else ("agotado" if o["productos"] else "no lo manejamos"),
    }


def h_buscar_vehiculo(texto):
    vehiculos = list(buscar_vehiculos(texto, limite=15))
    if not vehiculos:
        registrar_pendiente(texto, ConsultaPendiente.Canal.ASISTENTE)
        return {"encontrados": 0}
    return {"encontrados": len(vehiculos), "versiones": [{"id": v.pk, "descripcion": str(v)} for v in vehiculos]}


def h_filtros_del_vehiculo(vehiculo_id):
    v = Vehiculo.objects.filter(pk=vehiculo_id).first()
    if not v:
        return {"error": "No existe ese vehículo; búscalo primero con buscar_vehiculo."}
    return {
        "vehiculo": str(v),
        "filtros": [{"tipo": g["nombre"], "opciones": [_opcion_publica(o) for o in g["opciones"]]} for g in piezas_para(v)],
    }


def h_buscar_numero_parte(numero):
    r = buscar_numero(numero)
    if not r or not r["grupos"]:
        registrar_pendiente(f"Número {numero}", ConsultaPendiente.Canal.ASISTENTE)
        return {"encontrado": False}
    return {
        "encontrado": True,
        "grupos": [
            {**_opcion_publica(g), "tipo": g["tipo"], "vehiculos_que_lo_usan": g["vehiculos_n"],
             "ejemplos": [str(v) for v in g["vehiculos"][:6]]}
            for g in r["grupos"]
        ],
    }


def h_registrar_sin_respuesta(pregunta):
    registrar_pendiente(pregunta, ConsultaPendiente.Canal.ASISTENTE)
    return {"registrada": True}


EJECUTORES = {
    "buscar_vehiculo": h_buscar_vehiculo,
    "filtros_del_vehiculo": h_filtros_del_vehiculo,
    "buscar_numero_parte": h_buscar_numero_parte,
    "registrar_sin_respuesta": h_registrar_sin_respuesta,
}


def ejecutar(nombre, entrada):
    try:
        return json.dumps(EJECUTORES[nombre](**entrada), ensure_ascii=False), False
    except Exception:  # noqa: BLE001 - el error va de regreso al modelo, no tumba la conversación
        log.exception("Falló la herramienta %s", nombre)
        return "Error interno al consultar. Ofrece que el mostrador lo confirme.", True


# ---------------------------------------------------------------- conversación


def _llave_gasto():
    return f"asistente:gasto:{timezone.localdate().isoformat()}"


def gasto_hoy():
    """Lo gastado hoy en Claude, en USD."""
    return (cache.get(_llave_gasto()) or 0) / 1_000_000


def registrar_gasto(modelo, uso):
    entrada, salida, escritura, lectura = PRECIOS.get(modelo, PRECIOS["claude-opus-5-5"])
    # En millonésimas de dólar, para poder sumar con incr.
    micro = round(
        uso.input_tokens * entrada + uso.output_tokens * salida
        + (uso.cache_creation_input_tokens or 0) * escritura + (uso.cache_read_input_tokens or 0) * lectura
    )
    llave = _llave_gasto()
    if not cache.add(llave, micro, 60 * 60 * 26):
        try:
            cache.incr(llave, micro)
        except ValueError:
            cache.add(llave, micro, 60 * 60 * 26)


def con_ia():
    """Claude solo si hay credencial y no se ha llegado al tope de gasto del día."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False
    if gasto_hoy() >= settings.ASISTENTE_TOPE_DIARIO_USD:
        log.warning("Asistente en modo básico: se llegó al tope diario de %s USD", settings.ASISTENTE_TOPE_DIARIO_USD)
        return False
    return True


def responder(historial, texto):
    """Agrega el mensaje al historial (lista de mensajes de la API) y devuelve el texto de respuesta."""
    if sum(1 for m in historial if m["role"] == "user" and isinstance(m["content"], str)) >= MAX_TURNOS:
        return "Esta conversación ya va muy larga. Toca «Nueva conversación» y seguimos."
    if not con_ia():
        return responder_basico(historial, texto)
    return responder_claude(historial, texto)


def responder_claude(historial, texto):
    import anthropic

    client = anthropic.Anthropic()
    modelo = settings.ASISTENTE_MODELO
    # Opus y Sonnet pueden rechazar por clasificadores; con fallbacks la API reintenta en otro modelo.
    # Haiku no tiene ese respaldo en el servidor.
    respaldo = {} if modelo.startswith("claude-haiku") else {
        "betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default",
    }
    inicio = len(historial)
    historial.append({"role": "user", "content": texto})
    for _ in range(MAX_VUELTAS):
        try:
            r = client.beta.messages.create(
                model=modelo,
                max_tokens=1500,
                system=SISTEMA,
                tools=HERRAMIENTAS,
                messages=historial,
                output_config={"effort": "low"},
                cache_control={"type": "ephemeral"},
                **respaldo,
            )
        except anthropic.AuthenticationError:
            del historial[inicio:]  # el mensaje no se contestó: se descarta completo
            return "El asistente no está configurado (revisa ANTHROPIC_API_KEY)."
        except anthropic.RateLimitError:
            del historial[inicio:]
            return "Hay muchas consultas en este momento. Intenta de nuevo en un minuto."
        except (anthropic.APIConnectionError, anthropic.APIStatusError):
            log.exception("Error de la API de Claude")
            del historial[inicio:]
            return "No pude conectarme. Intenta de nuevo o llama a la tienda."

        registrar_gasto(modelo, r.usage)
        historial.append({"role": "assistant", "content": [b.to_dict() for b in r.content]})
        if r.stop_reason == "refusal":
            return "Eso no lo puedo contestar. Si buscas un filtro, dime marca, modelo y año de tu vehículo."
        usos = [b for b in r.content if b.type == "tool_use"]
        if r.stop_reason != "tool_use" or not usos:
            return "".join(b.text for b in r.content if b.type == "text").strip() or "¿Me repites tu vehículo?"
        resultados = []
        for b in usos:
            contenido, error = ejecutar(b.name, b.input)
            resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": contenido, "is_error": error})
        historial.append({"role": "user", "content": resultados})
    return "Me tardé demasiado en encontrarlo. ¿Me das marca, modelo y año otra vez?"


# ---------------------------------------------------------------- modo básico (sin IA)

PARECE_NUMERO = re.compile(r"\b(?:[A-Za-z]{1,5}-?\d{2,6}[A-Za-z]{0,3}|\d{5})\b")


def _pesos(n):
    return f"${n:,.0f}"


def _texto_opcion(o):
    partes = [f"Gonher {o['numero_gonher']}"]
    eq = [f"{e['marca']} {e['numero']}" + ("" if e["confirmada"] else " (por confirmar)") for e in o["equivalencias"]]
    if eq:
        partes.append("equivale a " + ", ".join(eq))
    if o["en_tienda"]:
        tenemos = ", ".join(f"{p['marca']} {p['numero']} a {_pesos(p['precio'])}" for p in o["en_tienda"])
        partes.append(f"lo tenemos: {tenemos}")
    elif o["estado"] == "agotado":
        partes.append("ahorita está agotado")
    else:
        partes.append("no lo manejamos, se puede pedir")
    return " · ".join(partes)


def responder_basico(historial, texto):
    historial.append({"role": "user", "content": texto})
    limpio = texto.strip()

    # Un número de parte dentro del mensaje (PH7317, GP-149, 51356). "NP300" también lo parece, por eso
    # solo se contesta como número si el catálogo lo conoce.
    for candidato in PARECE_NUMERO.findall(limpio):
        if buscar_numero(candidato):
            datos = h_buscar_numero_parte(candidato)
            lineas = [f"{g['tipo']} {_texto_opcion(g)}. Le queda a {g['vehiculos_que_lo_usan']} versiones de vehículo."
                      for g in datos.get("grupos", [])]
            if lineas:
                return _cerrar(historial, "\n".join(lineas))

    # Si solo mandó el año o el motor, se completa con el vehículo que preguntó antes.
    anio, motor, palabras = interpretar(limpio)
    previo = next((m.get("vehiculo") for m in reversed(historial) if m.get("vehiculo")), "")
    consulta = limpio if palabras or not previo else f"{previo} {limpio}"

    datos = h_buscar_vehiculo(consulta)
    if not datos["encontrados"]:
        return _cerrar(historial, "No encontré ese vehículo. Dime marca, modelo y año (ej. «Versa 2015»). "
                                  "Si es correcto, ya lo anoté para que en mostrador te confirmen.")
    historial[-1]["vehiculo"] = consulta
    if datos["encontrados"] > 1:
        lista = "\n".join(f"• {v['descripcion']}" for v in datos["versiones"][:8])
        return _cerrar(historial, f"Encontré varias versiones:\n{lista}\n¿Cuál es? Escríbeme el año y el motor.")
    filtros = h_filtros_del_vehiculo(datos["versiones"][0]["id"])
    lineas = [f"Para {filtros['vehiculo']}:"]
    for f in filtros["filtros"]:
        for o in f["opciones"]:
            lineas.append(f"• {f['tipo']}: {_texto_opcion(o)}")
    lineas.append("Para apartarlo o comprarlo, en mostrador te atienden.")
    return _cerrar(historial, "\n".join(lineas))


def _cerrar(historial, respuesta):
    historial.append({"role": "assistant", "content": respuesta})
    return respuesta
