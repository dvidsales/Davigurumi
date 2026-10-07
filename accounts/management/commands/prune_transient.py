"""Remove only expired transient data, never domain or financial history."""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from accounts.models import AuthThrottle
from django.contrib.sessions.models import Session
from portability.models import ImportJob


class Command(BaseCommand):
    help = "Mostra contagem de sessões/limites expirados e prévias antigas; --apply remove somente esses dados transitórios."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        rows = [
            (
                "Limites expirados",
                AuthThrottle.objects.filter(expires_at__lt=now - timedelta(days=1)),
            ),
            ("Sessões expiradas", Session.objects.filter(expire_date__lt=now)),
            (
                "Prévias com mais de 30 dias",
                ImportJob.objects.filter(created_at__lt=now - timedelta(days=30)),
            ),
        ]
        for label, query in rows:
            count = query.count()
            if options["apply"]:
                query.delete()
            self.stdout.write(f"{label}: {count}.")
        self.stdout.write(
            "Dados transitórios removidos."
            if options["apply"]
            else "Simulação: nenhum dado alterado. Use --apply para efetivar."
        )
