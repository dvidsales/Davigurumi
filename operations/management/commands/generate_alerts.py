from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from operations.services import generate_alerts


class Command(BaseCommand):
    help = (
        "Gera alertas internos de reposição, prazo e parcelas. Não inicia um agendador."
    )

    def handle(self, *args, **options):
        count = 0
        for owner in get_user_model().objects.filter(
            is_active=True, demo_identity__isnull=True
        ):
            count += generate_alerts(owner)
        self.stdout.write(
            f"{count} novos alertas. Repetir no mesmo dia não duplica cada evento."
        )
