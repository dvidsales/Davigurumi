from importlib import import_module
from django.db import migrations


def refresh(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            import_module("sales.migrations.0002_database_guards").SQL
        )


class Migration(migrations.Migration):
    dependencies = [("sales", "0002_database_guards")]
    operations = [migrations.RunPython(refresh, migrations.RunPython.noop)]
