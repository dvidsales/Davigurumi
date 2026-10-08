import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from config.storage import SupabasePrivateStorage
from accounts.privacy import ledger_records


class Command(BaseCommand):
    help = (
        "Valida requisitos do beta privado, sem cadastrar usuários ou enviar convites."
    )

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")

    def handle(self, *args, **options):
        checks = {
            "beta_enabled": settings.BETA_MODE,
            "debug_disabled": not settings.DEBUG,
            "signup_invite_only": not settings.PUBLIC_SIGNUP_ENABLED
            and bool(settings.BETA_EMAILS),
            "trusted_https_proxy": settings.TRUSTED_PROXY
            and settings.SESSION_COOKIE_SECURE
            and settings.CSRF_COOKIE_SECURE,
            "postgresql_tls": connection.vendor == "postgresql"
            and connection.settings_dict.get("OPTIONS", {}).get("sslmode")
            == "verify-full",
        }
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_schema()")
                schema = cursor.fetchone()[0]
                checks["private_schema"] = (
                    schema == settings.POSTGRES_SCHEMA
                    and schema not in (None, "public")
                )
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_namespace n, LATERAL aclexplode(COALESCE(n.nspacl, acldefault('n',n.nspowner))) a WHERE n.nspname=current_schema() AND a.grantee=0 AND a.privilege_type IN ('USAGE','CREATE'))"
                )
                checks["no_public_schema_grant"] = not cursor.fetchone()[0]
                cursor.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
                checks["restricted_role"] = not any(cursor.fetchone())
                cursor.execute(
                    "SELECT has_schema_privilege(oid, current_schema(), 'USAGE') FROM pg_roles WHERE rolname IN ('anon','authenticated')"
                )
                checks["no_public_api_schema_access"] = not any(
                    row[0] for row in cursor.fetchall()
                )
        else:
            checks.update(
                private_schema=False,
                restricted_role=False,
                no_public_api_schema_access=False,
                no_public_schema_grant=False,
            )
        try:
            SupabasePrivateStorage().check_private()
            ledger_records()
            checks["private_persistent_files_and_ledger"] = True
        except (ValidationError, OSError, ValueError):
            checks["private_persistent_files_and_ledger"] = False
        checks["independent_ledger_key"] = bool(
            settings.PRIVACY_LEDGER_KEY
            and settings.PRIVACY_LEDGER_KEY != settings.SECRET_KEY
        )
        ready = all(checks.values())
        self.stdout.write(
            json.dumps(
                {
                    "checks": checks,
                    "ready_for_private_beta": ready,
                    "public_launch_reviewed": False,
                }
            )
        )
        if options["strict"] and not ready:
            raise CommandError(
                "Beta bloqueado: confira os requisitos acima. Nenhum segredo foi impresso."
            )
