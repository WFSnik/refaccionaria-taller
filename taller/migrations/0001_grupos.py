from django.db import migrations

GRUPOS = ["Mostrador", "Ventas", "Almacén", "Compras", "Contabilidad", "Seguridad"]


def crear(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


class Migration(migrations.Migration):
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
