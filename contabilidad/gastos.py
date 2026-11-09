"""Entrada de los costos que registran otros módulos (compras, seguridad). Va aparte para no crear ciclos de imports."""

from .models import Gasto


def registrar_gasto(*, categoria, concepto, monto, usuario, referencia=""):
    return Gasto.objects.create(categoria=categoria, concepto=concepto, monto=monto, referencia=referencia, usuario=usuario)
