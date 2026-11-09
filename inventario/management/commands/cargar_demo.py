"""Carga catálogo de ejemplo (aceites, filtros, líquidos, empaques, bujías, bandas y plumas) con existencias iniciales."""

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.models import Categoria, Marca, Movimiento, Producto, Ubicacion
from inventario.services import registrar_alta, registrar_baja

CATEGORIAS = [
    ("Aceites de motor", "Minerales, semisintéticos y sintéticos"),
    ("Aceites de transmisión", "ATF, CVT y aceites para engranes"),
    ("Filtros de aceite", ""),
    ("Filtros de aire", ""),
    ("Filtros de gasolina", ""),
    ("Filtros de cabina", ""),
    ("Anticongelantes", "Refrigerantes listos para usar y concentrados"),
    ("Líquidos de frenos", ""),
    ("Aditivos", "Limpiadores de inyectores, tratamientos de aceite"),
    ("Empaques y juntas", "Tapa de punterías, cárter, cabeza, múltiple, termostato y roldanas de tapón"),
    ("Selladores y grasas", "Silicón formador de juntas, fijadores de rosca y grasas"),
    ("Bujías", "Cobre, platino e iridio"),
    ("Bandas", "Bandas de accesorios (poly-V) y de distribución"),
    ("Plumas limpiaparabrisas", "Convencionales y de una pieza (flat)"),
]

UBICACIONES = [
    ("A-01-1", "Pasillo A, estante 1, nivel 1"),
    ("A-01-2", "Pasillo A, estante 1, nivel 2"),
    ("A-02-1", "Pasillo A, estante 2, nivel 1"),
    ("B-01-1", "Pasillo B, estante 1, nivel 1"),
    ("B-01-2", "Pasillo B, estante 1, nivel 2"),
    ("B-02-1", "Pasillo B, estante 2, nivel 1"),
    ("C-01-1", "Pasillo C, cubetas y garrafas"),
    ("MOST-1", "Mostrador, exhibidor"),
    ("D-01-1", "Pasillo D, estante 1, empaques y bujías"),
    ("D-02-1", "Pasillo D, bandas colgadas y plumas"),
]

# (código, nombre, categoría, marca, presentación, especificación, costo, precio, reorden, ubicación, stock)
PRODUCTOS = [
    ("AM-0001", "Aceite sintético 5W-30", "Aceites de motor", "Mobil", "946 ml", "5W-30 API SP", 128, 189, 24, "A-01-1", 60),
    ("AM-0002", "Aceite sintético 5W-30", "Aceites de motor", "Mobil", "4.73 L", "5W-30 API SP", 560, 799, 8, "C-01-1", 14),
    ("AM-0003", "Aceite semisintético 10W-30", "Aceites de motor", "Castrol", "946 ml", "10W-30 API SP", 104, 155, 24, "A-01-1", 30),
    ("AM-0004", "Aceite multigrado 20W-50", "Aceites de motor", "Quaker State", "946 ml", "20W-50 API SL", 82, 125, 30, "A-01-2", 22),
    ("AM-0005", "Aceite sintético 0W-20", "Aceites de motor", "Valvoline", "946 ml", "0W-20 API SP", 139, 209, 18, "A-01-2", 36),
    ("AM-0006", "Aceite para motor diésel 15W-40", "Aceites de motor", "Roshfrans", "4 L", "15W-40 API CK-4", 470, 689, 6, "C-01-1", 5),
    ("AM-0007", "Aceite multigrado 25W-60", "Aceites de motor", "Bardahl", "946 ml", "25W-60 API SL", 88, 135, 12, "A-02-1", 16),
    ("AT-0001", "Aceite para transmisión automática", "Aceites de transmisión", "Valvoline", "946 ml", "ATF Dexron VI", 135, 199, 12, "A-02-1", 20),
    ("AT-0002", "Aceite para transmisión CVT", "Aceites de transmisión", "Castrol", "946 ml", "CVT", 189, 279, 6, "A-02-1", 4),
    ("AT-0003", "Aceite para engranes 80W-90", "Aceites de transmisión", "Roshfrans", "946 ml", "80W-90 API GL-5", 96, 145, 10, "A-02-1", 18),
    ("FA-0001", "Filtro de aceite", "Filtros de aceite", "Fram", "Pieza", "", 68, 115, 15, "B-01-1", 42),
    ("FA-0002", "Filtro de aceite", "Filtros de aceite", "Wix", "Pieza", "", 74, 125, 15, "B-01-1", 12),
    ("FA-0003", "Filtro de aceite", "Filtros de aceite", "Gonher", "Pieza", "", 52, 89, 20, "B-01-2", 35),
    ("FA-0004", "Filtro de aceite de cartucho", "Filtros de aceite", "Mann-Filter", "Pieza", "", 115, 179, 8, "B-01-2", 0),
    ("FI-0001", "Filtro de aire de motor", "Filtros de aire", "Fram", "Pieza", "", 145, 229, 10, "B-02-1", 18),
    ("FI-0002", "Filtro de aire de motor", "Filtros de aire", "Interfil", "Pieza", "", 98, 159, 10, "B-02-1", 9),
    ("FG-0001", "Filtro de gasolina", "Filtros de gasolina", "Gonher", "Pieza", "", 78, 129, 8, "B-02-1", 15),
    ("FC-0001", "Filtro de cabina con carbón activado", "Filtros de cabina", "Mann-Filter", "Pieza", "", 165, 259, 6, "B-02-1", 10),
    ("AC-0001", "Anticongelante listo para usar 50/50", "Anticongelantes", "Prestone", "3.78 L", "Verde, 50/50", 165, 239, 10, "C-01-1", 24),
    ("AC-0002", "Anticongelante concentrado", "Anticongelantes", "Bardahl", "3.78 L", "Rosa, larga duración", 210, 305, 6, "C-01-1", 3),
    ("LF-0001", "Líquido de frenos", "Líquidos de frenos", "Roshfrans", "350 ml", "DOT 3", 48, 79, 12, "MOST-1", 25),
    ("LF-0002", "Líquido de frenos", "Líquidos de frenos", "Bosch", "500 ml", "DOT 4", 85, 135, 8, "MOST-1", 11),
    ("AD-0001", "Limpiador de inyectores", "Aditivos", "Bardahl", "354 ml", "", 72, 119, 10, "MOST-1", 28),
    ("AD-0002", "Tratamiento para aceite de motor", "Aditivos", "STP", "443 ml", "", 89, 145, 6, "MOST-1", 7),
    ("EM-0001", "Empaque de tapa de punterías", "Empaques y juntas", "Fel-Pro", "Pieza", "Hule", 185, 289, 4, "D-01-1", 6),
    ("EM-0002", "Empaque de tapa de punterías", "Empaques y juntas", "TF Victor", "Pieza", "Hule", 120, 195, 4, "D-01-1", 3),
    ("EM-0003", "Empaque de cárter", "Empaques y juntas", "Victor Reinz", "Pieza", "Corcho-hule", 160, 249, 3, "D-01-1", 5),
    ("EM-0004", "Junta de cabeza", "Empaques y juntas", "Fel-Pro", "Pieza", "Multicapa de acero (MLS)", 690, 1050, 2, "D-01-1", 2),
    ("EM-0005", "Junta de múltiple de escape", "Empaques y juntas", "TF Victor", "Pieza", "", 95, 155, 4, "D-01-1", 7),
    ("EM-0006", "Empaque de termostato", "Empaques y juntas", "TF Victor", "Pieza", "", 28, 49, 8, "D-01-1", 14),
    ("EM-0007", "Roldana de tapón de cárter", "Empaques y juntas", "TF Victor", "Pieza", "Cobre, 14 mm", 6, 15, 40, "MOST-1", 85),
    ("EM-0008", "Roldana de tapón de cárter", "Empaques y juntas", "TF Victor", "Pieza", "Aluminio, 12 mm", 5, 12, 40, "MOST-1", 30),
    ("SE-0001", "Silicón formador de juntas", "Selladores y grasas", "Permatex", "85 g", "Rojo, alta temperatura", 89, 139, 8, "MOST-1", 15),
    ("SE-0002", "Silicón formador de juntas", "Selladores y grasas", "Loctite", "80 ml", "Gris, para motor", 115, 179, 6, "MOST-1", 4),
    ("SE-0003", "Fijador de roscas", "Selladores y grasas", "Loctite", "6 ml", "Azul, resistencia media", 95, 149, 6, "MOST-1", 9),
    ("SE-0004", "Grasa multiusos", "Selladores y grasas", "Roshfrans", "450 g", "Litio, NLGI 2", 78, 125, 6, "A-02-1", 11),
    ("BU-0001", "Bujía de cobre", "Bujías", "Champion", "Pieza", "Cobre", 38, 65, 24, "D-01-1", 64),
    ("BU-0002", "Bujía de platino", "Bujías", "NGK", "Pieza", "Platino", 95, 155, 16, "D-01-1", 40),
    ("BU-0003", "Bujía de iridio", "Bujías", "NGK", "Pieza", "Iridio", 175, 279, 16, "D-01-1", 12),
    ("BU-0004", "Bujía de iridio", "Bujías", "Denso", "Pieza", "Iridio", 165, 265, 8, "D-01-1", 20),
    ("BA-0001", "Banda de accesorios poly-V", "Bandas", "Gates", "Pieza", "6 costillas", 260, 399, 4, "D-02-1", 7),
    ("BA-0002", "Banda de accesorios poly-V", "Bandas", "Dayco", "Pieza", "4 costillas", 190, 299, 4, "D-02-1", 3),
    ("BA-0003", "Banda de distribución", "Bandas", "Gates", "Pieza", "Dentada", 340, 529, 2, "D-02-1", 4),
    ("PL-0001", "Pluma limpiaparabrisas convencional", "Plumas limpiaparabrisas", "Bosch", "Pieza", "20 pulgadas", 85, 139, 8, "D-02-1", 16),
    ("PL-0002", "Pluma limpiaparabrisas de una pieza", "Plumas limpiaparabrisas", "Bosch", "Pieza", "22 pulgadas", 165, 259, 6, "D-02-1", 9),
    ("PL-0003", "Pluma limpiaparabrisas de una pieza", "Plumas limpiaparabrisas", "Rain-X", "Pieza", "18 pulgadas", 150, 239, 6, "D-02-1", 2),
]


class Command(BaseCommand):
    help = "Carga categorías, marcas, ubicaciones y productos de ejemplo con movimientos iniciales."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", required=True, help="Usuario que quedará como autor de los movimientos.")

    @transaction.atomic
    def handle(self, *args, usuario, **opts):
        User = get_user_model()
        try:
            autor = User.objects.get(username=usuario)
        except User.DoesNotExist:
            raise CommandError(f"No existe el usuario {usuario!r}. Créalo con createsuperuser.")
        categorias = {n: Categoria.objects.get_or_create(nombre=n, defaults={"descripcion": d})[0] for n, d in CATEGORIAS}
        ubicaciones = {c: Ubicacion.objects.get_or_create(codigo=c, defaults={"descripcion": d})[0] for c, d in UBICACIONES}
        rnd = random.Random(7)
        creados = 0

        for i, (codigo, nombre, cat, marca, pres, esp, costo, precio, reorden, ubic, stock) in enumerate(PRODUCTOS):
            # Los productos que ya existen se dejan como están, para no duplicar sus movimientos.
            if Producto.objects.filter(codigo=codigo).exists():
                continue
            creados += 1
            producto, _ = Producto.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "codigo_barras": f"75010{i:07d}{rnd.randint(0, 9)}",
                    "nombre": nombre,
                    "categoria": categorias[cat],
                    "marca": Marca.objects.get_or_create(nombre=marca)[0],
                    "presentacion": pres,
                    "especificacion": esp,
                    "costo": costo,
                    "precio_venta": precio,
                    "punto_reorden": reorden,
                },
            )
            # Entra más de lo que queda y luego se registran ventas, para que haya historial.
            entrada = stock + rnd.randint(4, 14)
            registrar_alta(
                producto=producto, ubicacion=ubicaciones[ubic], cantidad=entrada,
                motivo=Movimiento.Motivo.COMPRA, usuario=autor, referencia=f"FAC-{2400 + i}",
            )
            registrar_baja(
                producto=producto, ubicacion=ubicaciones[ubic], cantidad=entrada - stock,
                motivo=Movimiento.Motivo.VENTA, usuario=autor, referencia=f"TK-{9100 + i}",
            )

        self.stdout.write(self.style.SUCCESS(f"Listo: {creados} productos nuevos ({len(PRODUCTOS) - creados} ya existían) en {len(UBICACIONES)} ubicaciones."))
