from django.db import migrations


def backfill(apps, schema_editor):
    Movement = apps.get_model("materials", "StockMovement")
    Layer = apps.get_model("materials", "CostLayer")
    for movement in Movement.objects.filter(
        layer__isnull=True, kind="opening"
    ).iterator():
        layer = Layer.objects.create(
            material_id=movement.material_id,
            original_quantity=movement.quantity,
            physical=movement.quantity,
            unit_cost=movement.unit_cost,
        )
        movement.layer_id = layer.pk
        movement.save(update_fields=["layer"])


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0004_costlayer_materialconversion_reservationevent_and_more")
    ]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
