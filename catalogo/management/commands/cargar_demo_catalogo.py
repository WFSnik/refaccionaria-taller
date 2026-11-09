"""Agrega filtros de ejemplo con número de parte real para que el buscador por vehículo muestre existencias."""

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.models import Categoria, Marca, Movimiento, Producto, Ubicacion
from inventario.services import registrar_alta, registrar_baja

ACEITE, AIRE, CABINA, GASOLINA = "Filtros de aceite", "Filtros de aire", "Filtros de cabina", "Filtros de gasolina"

# (código, marca, número de parte, nombre, categoría, costo, precio, reorden, ubicación, stock)
# Las aplicaciones de cada número salen del catálogo; el comentario es solo para ubicarlos.
FILTROS = [
    ("FA-0101", "Gonher", "GP-149", "Filtro de aceite", ACEITE, 52, 89, 12, "B-01-2", 18),  # Versa, March, CR-V
    ("FA-0102", "Gonher", "GPS-149", "Filtro de aceite para sintético", ACEITE, 78, 129, 6, "B-01-2", 6),
    ("FA-0103", "Fram", "PH7317", "Filtro de aceite Extra Guard", ACEITE, 68, 115, 10, "B-01-1", 0),
    ("FA-0104", "Wix", "51356", "Filtro de aceite", ACEITE, 74, 125, 6, "B-01-1", 4),
    ("FA-0105", "Gonher", "GP-91", "Filtro de aceite", ACEITE, 52, 89, 10, "B-01-2", 9),  # Sentra, X-Trail
    ("FA-0106", "Fram", "PH6607", "Filtro de aceite Extra Guard", ACEITE, 68, 115, 8, "B-01-1", 7),
    ("FA-0107", "Gonher", "GP-156", "Filtro de aceite", ACEITE, 49, 85, 10, "B-01-2", 14),  # Tsuru 2009-2017
    ("FA-0108", "Gonher", "GP-46", "Filtro de aceite", ACEITE, 52, 89, 10, "B-01-2", 3),  # Aveo 1.6
    ("FA-0109", "Gonher", "GP-409", "Filtro de aceite", ACEITE, 55, 95, 8, "B-01-2", 11),  # Beat, Aveo 1.5
    ("FA-0110", "Gonher", "GP-561", "Filtro de aceite", ACEITE, 79, 135, 6, "B-01-2", 5),  # Vento 1.6
    ("FA-0111", "Gonher", "G-911", "Filtro de aceite de cartucho", ACEITE, 85, 145, 6, "B-01-2", 4),  # Corolla 1.8
    ("FA-0112", "Gonher", "GP-28", "Filtro de aceite", ACEITE, 52, 89, 8, "B-01-2", 10),  # Jetta A4
    ("FI-0101", "Gonher", "GA-306", "Filtro de aire de motor", AIRE, 98, 165, 6, "B-02-1", 8),
    ("FI-0102", "Fram", "CA11215", "Filtro de aire de motor Extra Guard", AIRE, 145, 229, 4, "B-02-1", 3),
    ("FI-0103", "Gonher", "GAD-117", "Filtro de aire de motor", AIRE, 92, 155, 6, "B-02-1", 7),
    ("FI-0104", "Gonher", "GA-324", "Filtro de aire de motor", AIRE, 95, 159, 6, "B-02-1", 0),
    ("FI-0105", "Gonher", "GA-330", "Filtro de aire de motor", AIRE, 95, 159, 4, "B-02-1", 5),
    ("FI-0106", "Gonher", "GAVW-630", "Filtro de aire de motor", AIRE, 110, 185, 4, "B-02-1", 4),
    ("FC-0101", "Gonher", "GAC-2271", "Filtro de cabina", CABINA, 120, 199, 4, "B-02-1", 6),
    ("FC-0102", "Gonher", "GAC-2287", "Filtro de cabina", CABINA, 120, 199, 4, "B-02-1", 2),
    ("FC-0103", "Fram", "CF12237", "Filtro de cabina Fresh Breeze", CABINA, 165, 259, 3, "B-02-1", 2),
    ("FG-0101", "Gonher", "GG-137", "Filtro de gasolina", GASOLINA, 78, 129, 6, "B-02-1", 9),
    ("FG-0102", "Gonher", "GG-419", "Filtro de gasolina", GASOLINA, 85, 139, 4, "B-02-1", 3),
]


class Command(BaseCommand):
    help = "Crea filtros de ejemplo con número de parte y stock. Los que ya existen se dejan como están."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", required=True, help="Usuario que quedará como autor de los movimientos.")

    @transaction.atomic
    def handle(self, *args, usuario, **opts):
        try:
            autor = get_user_model().objects.get(username=usuario)
        except get_user_model().DoesNotExist:
            raise CommandError(f"No existe el usuario {usuario!r}. Créalo con createsuperuser.")

        rnd = random.Random(11)
        creados = 0
        for i, (codigo, marca, numero, nombre, cat, costo, precio, reorden, ubic, stock) in enumerate(FILTROS):
            if Producto.objects.filter(codigo=codigo).exists():
                continue
            producto = Producto.objects.create(
                codigo=codigo, nombre=nombre, numero_parte=numero,
                categoria=Categoria.objects.get_or_create(nombre=cat)[0],
                marca=Marca.objects.get_or_create(nombre=marca)[0],
                presentacion="Pieza", costo=costo, precio_venta=precio, punto_reorden=reorden,
            )
            ubicacion = Ubicacion.objects.get_or_create(codigo=ubic)[0]
            entrada = stock + rnd.randint(3, 10)
            registrar_alta(
                producto=producto, ubicacion=ubicacion, cantidad=entrada,
                motivo=Movimiento.Motivo.COMPRA, usuario=autor, referencia=f"FAC-{3100 + i}",
            )
            registrar_baja(
                producto=producto, ubicacion=ubicacion, cantidad=entrada - stock,
                motivo=Movimiento.Motivo.VENTA, usuario=autor, referencia=f"TK-{9600 + i}",
            )
            creados += 1
        self.stdout.write(self.style.SUCCESS(f"Listo: {creados} filtros nuevos ({len(FILTROS) - creados} ya existían)."))
