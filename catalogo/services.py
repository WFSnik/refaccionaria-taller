"""Búsquedas sobre el catálogo: qué lleva un vehículo, equivalencias y qué hay en el anaquel."""

import re
from collections import defaultdict

from django.db.models import Prefetch, Q

from inventario.models import Existencia, Producto

from .models import Aplicacion, ConsultaPendiente, Equivalencia, TipoPieza, Vehiculo, clave

ORDEN_TIPOS = [TipoPieza.ACEITE, TipoPieza.ACEITE_SINT, TipoPieza.AIRE, TipoPieza.CABINA, TipoPieza.GASOLINA]

# Palabras que la gente escribe al preguntar y que no ayudan a encontrar el vehículo.
VACIAS = {
    "de", "del", "mi", "mis", "para", "el", "la", "los", "las", "un", "una", "que", "qué", "y", "o", "con", "es",
    "filtro", "filtros", "aceite", "aire", "cabina", "gasolina", "combustible", "lleva", "llevan", "ocupo",
    "necesito", "busco", "carro", "auto", "coche", "camioneta", "modelo", "año", "motor", "tiene", "hay", "tienen",
    "sintetico", "sintético", "cual", "cuál", "le", "queda", "sirve", "precio", "cuanto", "cuánto",
    "tengo", "quiero", "me", "tu", "su", "por", "favor", "hola", "buenas", "buenos", "dias", "días", "tardes",
    "noches", "si", "sí", "no", "ese", "esa", "este", "esta", "equivalente", "cuesta", "vale", "tiene", "son",
}


def interpretar(texto):
    """Separa lo que escribió la persona en año, motor y palabras de marca o modelo."""
    anio, motor, palabras = None, None, []
    for t in re.findall(r"[\wÁÉÍÓÚÑáéíóúñ.\-]+", texto.lower()):
        if re.fullmatch(r"(19|20)\d\d", t):
            anio = int(t)
        elif re.fullmatch(r"\d\.\d(l)?", t):
            motor = t.rstrip("l")
        elif t not in VACIAS and len(t) > 1:
            palabras.append(t)
    return anio, motor, palabras


def buscar_vehiculos(texto="", *, marca="", modelo="", anio=None, motor="", limite=40):
    vehiculos = Vehiculo.objects.all()
    if texto:
        a, m, palabras = interpretar(texto)
        anio = anio or a
        motor = motor or m or ""
        for p in palabras:
            vehiculos = vehiculos.filter(busqueda__contains=clave(p))
        if not palabras:
            return Vehiculo.objects.none()
    if marca:
        vehiculos = vehiculos.filter(marca__iexact=marca)
    if modelo:
        vehiculos = vehiculos.filter(modelo__iexact=modelo)
    if anio:
        vehiculos = vehiculos.filter(anio_inicio__lte=anio, anio_fin__gte=anio)
    if motor:
        vehiculos = vehiculos.filter(motor__icontains=motor)
    return vehiculos[:limite]


def _productos_para(numeros_por_marca):
    """Productos activos del inventario cuyo (marca, número de parte) está en el conjunto dado."""
    filtro = Q()
    for marca, numeros in numeros_por_marca.items():
        filtro |= Q(marca__nombre__iexact=marca, numero_parte__in=[n.upper() for n in numeros])
    if not filtro:
        return []
    return list(
        Producto.objects.filter(activo=True)
        .filter(filtro)
        .con_stock()
        .select_related("marca")
        .prefetch_related(
            Prefetch("existencias", queryset=Existencia.objects.filter(cantidad__gt=0).select_related("ubicacion"))
        )
        .order_by("-stock", "precio_venta")
    )


def _armar_opciones(numeros_gonher):
    """Para cada número Gonher: sus equivalencias y lo que hay en inventario de cualquiera de ellos."""
    equivalencias = defaultdict(list)
    for e in Equivalencia.objects.filter(numero_gonher__in=numeros_gonher):
        equivalencias[e.numero_gonher].append(e)

    por_marca = defaultdict(set)
    for n in numeros_gonher:
        por_marca["Gonher"].add(n)
        for e in equivalencias[n]:
            por_marca[e.marca].add(e.numero)
    productos = _productos_para(por_marca)

    opciones = {}
    for n in numeros_gonher:
        validos = {("GONHER", n.upper())} | {(e.marca.upper(), e.numero.upper()) for e in equivalencias[n]}
        en_inventario = [p for p in productos if (p.marca.nombre.upper(), p.numero_parte) in validos]
        opciones[n] = {
            "numero_gonher": n,
            "equivalencias": equivalencias[n],
            "productos": en_inventario,
            "disponible": any(p.stock > 0 for p in en_inventario),
        }
    return opciones


def piezas_para(vehiculo):
    """Filtros que lleva el vehículo agrupados por tipo, con equivalencias y existencias."""
    aplicaciones = list(vehiculo.aplicaciones.all())
    opciones = _armar_opciones({a.numero_gonher for a in aplicaciones})
    grupos = []
    for tipo in ORDEN_TIPOS:
        numeros = sorted({a.numero_gonher for a in aplicaciones if a.tipo == tipo})
        if numeros:
            grupos.append({"tipo": tipo, "nombre": TipoPieza(tipo).label, "opciones": [opciones[n] for n in numeros]})
    return grupos


def buscar_numero(texto):
    """Encuentra un número de parte de cualquier marca y lo traduce a su grupo Gonher."""
    k = clave(texto)
    if len(k) < 3:
        return None
    gonher = set(Aplicacion.objects.filter(clave=k).values_list("numero_gonher", flat=True).distinct())
    gonher |= set(Equivalencia.objects.filter(clave=k).values_list("numero_gonher", flat=True))
    gonher |= {n for n in Equivalencia.objects.values_list("numero_gonher", flat=True).distinct() if clave(n) == k}
    sueltos = [
        p for p in Producto.objects.filter(activo=True).exclude(numero_parte="").con_stock().select_related("marca")
        if clave(p.numero_parte) == k
    ]
    if not gonher and not sueltos:
        return None
    opciones = _armar_opciones(gonher)
    grupos = []
    for n in sorted(gonher):
        aplica = Aplicacion.objects.filter(numero_gonher=n).select_related("vehiculo")
        grupos.append({
            **opciones[n],
            "tipo": TipoPieza(aplica[0].tipo).label if aplica else "",
            "vehiculos_n": aplica.count(),
            "vehiculos": [a.vehiculo for a in aplica.order_by("vehiculo__marca", "vehiculo__modelo", "-vehiculo__anio_fin")[:30]],
        })
    ya = {p.pk for g in grupos for p in g["productos"]}
    return {"buscado": texto.strip(), "grupos": grupos, "sin_catalogo": [p for p in sueltos if p.pk not in ya]}


def registrar_pendiente(texto, canal):
    texto = texto.strip()[:300]
    if texto:
        ConsultaPendiente.objects.get_or_create(texto=texto, canal=canal, atendida=False)
