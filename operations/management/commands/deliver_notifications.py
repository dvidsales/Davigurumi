from django.core.management.base import BaseCommand
from operations.services import deliver_outbox


class Command(BaseCommand):
    help = "Processa até 50 mensagens pendentes com deduplicação e backoff."

    def handle(self, **options):
        self.stdout.write(str(deliver_outbox()))
