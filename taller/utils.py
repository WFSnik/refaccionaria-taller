from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.shortcuts import render

CENTAVOS = Decimal("0.01")


class ReglaNegocio(Exception):
    """Una operación que el flujo no permite. El mensaje se le muestra tal cual al usuario."""


def totales(subtotal):
    """Regresa (subtotal, iva, total) redondeados a centavos. Los precios se capturan sin IVA."""
    subtotal = Decimal(subtotal).quantize(CENTAVOS, ROUND_HALF_UP)
    iva = (subtotal * settings.IVA_TASA).quantize(CENTAVOS, ROUND_HALF_UP)
    return subtotal, iva, subtotal + iva


def pagina_form(request, form, titulo, volver, descripcion="", boton="Guardar"):
    return render(
        request,
        "taller/form.html",
        {"form": form, "titulo": titulo, "descripcion": descripcion, "boton": boton, "volver": volver},
    )
