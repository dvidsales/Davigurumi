from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from materials.models import Material


class Command(BaseCommand):
    help = (
        "Compara saldos físicos/reservados com seus históricos, sem alterar registros."
    )

    def handle(self, **options):
        failures = []
        count = 0
        for material in (
            Material.objects.all()
            .prefetch_related("layers", "movements")
            .iterator(chunk_size=100)
        ):
            count += 1
            physical = sum(
                (layer.physical for layer in material.layers.all()), Decimal(0)
            )
            if physical != material.physical_stock:
                failures.append(str(material.pk))
            for layer in material.layers.all():
                reserved = sum(
                    (row.remaining for row in layer.reservations.all()), Decimal(0)
                )
                movements = sum(
                    (row.quantity for row in layer.movements.all()), Decimal(0)
                )
                if reserved != layer.reserved or movements != layer.physical:
                    failures.append(str(layer.pk))
        if failures:
            raise CommandError("Divergências em IDs: " + ", ".join(failures))
        self.stdout.write(
            self.style.SUCCESS(f"{count} materiais conciliados, sem divergências.")
        )
