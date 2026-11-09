from .roles import MODULOS, puede


def permisos(request):
    """`puede.ventas`, `puede.almacen`, etc. para el menú y los botones de las plantillas."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"puede": {}}
    return {"puede": {modulo: puede(user, modulo) for modulo in MODULOS}}
