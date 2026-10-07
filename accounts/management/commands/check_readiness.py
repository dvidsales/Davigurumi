"""Local preflight; no deployment or external request."""

import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from accounts.privacy import ledger_root, read_tombstone


class Command(BaseCommand):
    help = "Relata requisitos técnicos de produção sem publicar a aplicação. --strict falha quando incompletos."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")

    def handle(self, *args, **options):
        checks = {
            "debug_disabled": not settings.DEBUG,
            "https_redirect_and_cookies": settings.SECURE_SSL_REDIRECT
            and settings.SESSION_COOKIE_SECURE
            and settings.CSRF_COOKIE_SECURE,
            "public_signup_closed": not settings.PUBLIC_SIGNUP_ENABLED,
            "smtp_configured": settings.EMAIL_BACKEND
            == "django.core.mail.backends.smtp.EmailBackend"
            and bool(settings.EMAIL_HOST_USER)
            and bool(settings.EMAIL_HOST_PASSWORD)
            and settings.EMAIL_USE_TLS,
            "postgresql_with_required_tls": connection.vendor == "postgresql"
            and connection.settings_dict.get("OPTIONS", {}).get("sslmode")
            in {"require", "verify-ca", "verify-full"},
        }
        try:
            root = ledger_root()
            for path in root.glob("*.json"):
                read_tombstone(path.stem)
            checks["independent_erasure_ledger"] = bool(
                settings.PRIVACY_LEDGER_REQUIRED
                and settings.PRIVACY_LEDGER_KEY != settings.SECRET_KEY
            )
        except (ValidationError, ValueError, OSError):
            checks["independent_erasure_ledger"] = False
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
                )
                checks["restricted_database_role"] = not any(cursor.fetchone())
        else:
            checks["restricted_database_role"] = False
        self.stdout.write(
            json.dumps(
                {
                    "checks": checks,
                    "ready": all(checks.values()),
                    "manual_checks": [
                        "Domínio/proxy e permissões do armazenamento",
                        "Backup independente e ensaio de recuperação",
                        "Agendador e monitoramento",
                        "Política de retenção e revisão independente",
                        "Dispositivos reais",
                    ],
                },
                ensure_ascii=False,
            )
        )
        if options["strict"] and not all(checks.values()):
            raise CommandError(
                "Requisitos técnicos ainda incompletos; não abrir ao público."
            )
