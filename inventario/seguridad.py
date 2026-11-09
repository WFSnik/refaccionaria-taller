"""Límites de uso: mensajes del asistente por visitante e intentos de contraseña."""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.cache import cache


def ip_cliente(request):
    """IP real del visitante.

    En Railway el proxy escribe la IP de quien se conecta en X-Real-IP y reemplaza la que mande el cliente.
    X-Forwarded-For no sirve: su último valor es un nodo de Railway que cambia en cada petición.
    Fuera de Railway, REMOTE_ADDR.
    """
    if settings.EN_RAILWAY and request.META.get("HTTP_X_REAL_IP"):
        return request.META["HTTP_X_REAL_IP"].strip()
    return request.META.get("REMOTE_ADDR", "")


def contar(clave, ventana):
    """Suma 1 al contador de la ventana actual (en segundos) y devuelve el total."""
    llave = f"limite:{clave}:{ventana}:{int(time.time() // ventana)}"
    if cache.add(llave, 1, ventana + 5):
        return 1
    try:
        return cache.incr(llave)
    except ValueError:  # expiró entre add e incr
        cache.add(llave, 1, ventana + 5)
        return 1


VENTANAS = (60, 3600, 86400)


def excede_limite_asistente(request):
    """Cuenta un mensaje del visitante y dice si ya pasó alguno de los límites por minuto, hora o día."""
    ip = ip_cliente(request)
    totales = [contar(f"asistente:{ip}", v) for v in VENTANAS]
    return any(t > limite for t, limite in zip(totales, settings.ASISTENTE_LIMITES_IP))


# ---------------------------------------------------------------- inicio de sesión

INTENTOS = 5
BLOQUEO = 15 * 60


def _llave_acceso(request):
    return f"acceso:{ip_cliente(request)}"


class LoginLimitado(auth_views.LoginView):
    """Después de 5 contraseñas equivocadas desde la misma IP, bloquea los intentos 15 minutos."""

    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if (cache.get(_llave_acceso(request)) or 0) >= INTENTOS:
            messages.error(request, "Demasiados intentos. Espera 15 minutos e intenta de nuevo.")
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        llave = _llave_acceso(self.request)
        if not cache.add(llave, 1, BLOQUEO):
            try:
                cache.incr(llave)
            except ValueError:
                cache.add(llave, 1, BLOQUEO)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_llave_acceso(self.request))
        return super().form_valid(form)
