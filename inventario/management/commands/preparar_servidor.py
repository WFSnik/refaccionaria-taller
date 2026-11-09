"""Deja lista una base nueva al desplegar: admin, catálogo y, si se pide, datos de ejemplo. Se puede correr siempre."""

import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from catalogo.models import Vehiculo


class Command(BaseCommand):
    help = "Crea el admin con DJANGO_SUPERUSER_USERNAME/PASSWORD si no hay ninguno y carga el catálogo si está vacío."

    def handle(self, *args, **opts):
        User = get_user_model()
        usuario = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        if usuario and os.environ.get("DJANGO_SUPERUSER_PASSWORD") and not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(usuario, os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
                                          os.environ["DJANGO_SUPERUSER_PASSWORD"])
            self.stdout.write(f"Admin {usuario} creado.")

        if not Vehiculo.objects.exists():
            call_command("cargar_catalogo", stdout=self.stdout)

        # Las dos cargas de ejemplo saltan lo que ya existe: así un despliegue agrega los productos nuevos.
        if os.environ.get("CARGAR_DEMO") == "1" and usuario:
            call_command("cargar_demo", usuario=usuario, stdout=self.stdout)
            call_command("cargar_demo_catalogo", usuario=usuario, stdout=self.stdout)
            # Un ejemplo que no se pudo cargar no debe impedir que el sitio arranque.
            try:
                call_command("cargar_demo_taller", usuario=usuario, stdout=self.stdout)
            except CommandError as e:
                self.stderr.write(f"No se cargó el ejemplo del taller: {e}")
