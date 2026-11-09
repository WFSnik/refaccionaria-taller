"""Quién entra a cada módulo. Los grupos los crea la migración taller/0001 y se asignan en /admin/."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

MOSTRADOR = "Mostrador"
VENTAS = "Ventas"
ALMACEN = "Almacén"
COMPRAS = "Compras"
CONTABILIDAD = "Contabilidad"
SEGURIDAD = "Seguridad"
GRUPOS = [MOSTRADOR, VENTAS, ALMACEN, COMPRAS, CONTABILIDAD, SEGURIDAD]

MODULOS = {
    "clientes": {MOSTRADOR, VENTAS},
    "mostrador": {MOSTRADOR},
    "ventas": {VENTAS},
    "almacen": {ALMACEN},
    "proveedores": {COMPRAS},
    "contabilidad": {CONTABILIDAD},
    "sst": {SEGURIDAD},
    # Consultar las órdenes de trabajo y marcar una reparación como terminada.
    "ordenes": {MOSTRADOR, VENTAS, ALMACEN, CONTABILIDAD, SEGURIDAD},
    "terminar": {MOSTRADOR, VENTAS},
}


def grupos_de(user):
    if not hasattr(user, "_grupos_taller"):
        user._grupos_taller = set(user.groups.values_list("name", flat=True))
    return user._grupos_taller


def puede(user, modulo):
    if not user.is_authenticated:
        return False
    return user.is_superuser or bool(grupos_de(user) & MODULOS[modulo])


def modulo_requerido(modulo):
    """Pide sesión y responde 403 si el usuario no tiene un rol con acceso al módulo."""

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envuelta(request, *args, **kwargs):
            if not puede(request.user, modulo):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envuelta

    return decorador
