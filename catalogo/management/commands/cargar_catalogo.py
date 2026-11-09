"""Carga el catálogo de aplicaciones y equivalencias desde los CSV de catalogo/datos/."""

import csv
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Aplicacion, Equivalencia, Vehiculo, clave, clave_vehiculo

DATOS = Path(__file__).resolve().parents[2] / "datos"
FUENTE_GONHER = "Catálogo de filtros Gonher 2026 (gonher.com.mx)"


def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "Reemplaza vehículos, aplicaciones y equivalencias con los CSV de catalogo/datos/."

    @transaction.atomic
    def handle(self, *args, **opts):
        Aplicacion.objects.all().delete()
        Equivalencia.objects.all().delete()
        Vehiculo.objects.all().delete()

        filas = leer("gonher_aplicaciones_2026.csv")
        llaves = sorted({(f["marca"], f["modelo"], int(f["anio_inicio"]), int(f["anio_fin"]), f["motor"]) for f in filas})
        Vehiculo.objects.bulk_create(
            Vehiculo(marca=m, modelo=mo, anio_inicio=i, anio_fin=fi, motor=mot, busqueda=clave_vehiculo(m, mo))
            for m, mo, i, fi, mot in llaves
        )
        ids = {(v.marca, v.modelo, v.anio_inicio, v.anio_fin, v.motor): v.pk for v in Vehiculo.objects.all()}
        Aplicacion.objects.bulk_create(
            Aplicacion(
                vehiculo_id=ids[(f["marca"], f["modelo"], int(f["anio_inicio"]), int(f["anio_fin"]), f["motor"])],
                tipo=f["tipo"], numero_gonher=f["numero_gonher"], clave=clave(f["numero_gonher"]),
                fuente=f"Catálogo Gonher 2026, pág. {f['pagina']}",
            )
            for f in filas
        )

        equivalencias = {}
        fram_a_gonher = defaultdict(set)
        for f in leer("equivalencias_gonher_2026.csv"):
            fram_a_gonher[f["numero"]].add(f["numero_gonher"])
            equivalencias[(f["numero_gonher"], f["marca"], f["numero"])] = Equivalencia(
                numero_gonher=f["numero_gonher"], marca=f["marca"], numero=f["numero"], clave=clave(f["numero"]),
                confianza=Equivalencia.Confianza.FABRICANTE,
                fuente=f"Tabla de equivalencias del {FUENTE_GONHER}, pág. {f['pagina']}",
            )
        # Wix no está en la tabla de Gonher: se llega a través de su equivalente Fram.
        sin_ruta = []
        for f in leer("equivalencias_wix.csv"):
            if not fram_a_gonher.get(f["numero_fram"]):
                sin_ruta.append(f["numero_wix"])
            for g in fram_a_gonher.get(f["numero_fram"], ()):
                equivalencias[(g, "Wix", f["numero_wix"])] = Equivalencia(
                    numero_gonher=g, marca="Wix", numero=f["numero_wix"], clave=clave(f["numero_wix"]),
                    confianza=f["confianza"], fuente=f"Equivale a Fram {f['numero_fram']}. {f['fuentes']}",
                )
        Equivalencia.objects.bulk_create(equivalencias.values())

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {len(ids)} vehículos, {len(filas)} aplicaciones y {len(equivalencias)} equivalencias."
        ))
        if sin_ruta:
            self.stdout.write(self.style.WARNING(f"Wix sin equivalente Fram en la tabla de Gonher: {', '.join(sin_ruta)}"))
