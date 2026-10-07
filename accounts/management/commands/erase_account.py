import json
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from accounts.privacy import erase_account


class Command(BaseCommand):
    help = "Prévia de exclusão administrativa; --apply é irreversível e requer conta suspensa e política aprovada."

    def add_arguments(self, parser):
        parser.add_argument("owner_id")
        parser.add_argument(
            "--case", required=True, help="UUID do procedimento administrativo"
        )
        parser.add_argument(
            "--policy",
            required=True,
            help="Identificador da política de retenção aprovada",
        )
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            result = erase_account(
                owner_id=options["owner_id"],
                case_id=options["case"],
                policy_reference=options["policy"],
                apply=options["apply"],
            )
        except (ValidationError, ValueError, OSError) as exc:
            raise CommandError(
                "Exclusão não concluída; confira política, registro externo e armazenamento. "
                + str(exc)
            ) from exc
        self.stdout.write(json.dumps(result))
