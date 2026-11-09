import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from inventario.seguridad import excede_limite_asistente

from . import bot


# Los historiales de Claude y del modo básico tienen formatos distintos: cada uno en su llave.
def _llaves():
    modo = "ia" if bot.con_ia() else "basico"
    return modo, f"asistente_{modo}", f"asistente_vista_{modo}"


def chat(request):
    modo, _, vista = _llaves()
    return render(request, "asistente/chat.html", {"mensajes": request.session.get(vista, []), "modo": modo})


@require_POST
def mensaje(request):
    try:
        texto = json.loads(request.body).get("texto", "").strip()
    except (ValueError, AttributeError):
        texto = ""
    if not texto:
        return JsonResponse({"error": "Escribe tu pregunta."}, status=400)
    texto = texto[:500]
    if excede_limite_asistente(request):
        return JsonResponse({"respuesta": "Vas muy rápido. Espera un momento y vuelve a escribir."}, status=429)

    modo, llave, vista = _llaves()
    historial = request.session.get(llave, [])
    respuesta = bot.responder(historial, texto)
    mensajes = request.session.get(vista, []) + [["cliente", texto], ["asistente", respuesta]]
    request.session[llave] = historial
    request.session[vista] = mensajes
    return JsonResponse({"respuesta": respuesta, "modo": modo})


@require_POST
def nueva(request):
    for llave in [k for k in request.session.keys() if k.startswith("asistente_")]:
        del request.session[llave]
    return redirect("asistente_chat")
