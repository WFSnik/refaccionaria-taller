from django import template

register = template.Library()


def estado_stock(stock, reorden):
    if stock <= 0:
        return "agotado"
    if stock <= reorden:
        return "bajo"
    return "ok"


@register.inclusion_tag("inventario/_nivel.html")
def nivel(stock, reorden, tamano=""):
    """Bayoneta de aceite: el llenado es el stock y la marca es el punto de reorden."""
    stock = stock or 0
    capacidad = max(reorden * 3, stock, 1)
    return {
        "stock": stock,
        "reorden": reorden,
        "pct": round(stock / capacidad * 100, 1),
        "reorden_pct": round(reorden / capacidad * 100, 1),
        "estado": estado_stock(stock, reorden),
        "tamano": tamano,
    }


@register.filter
def estado(stock, reorden):
    return estado_stock(stock or 0, reorden)
