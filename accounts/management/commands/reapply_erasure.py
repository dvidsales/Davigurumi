import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from accounts.privacy import ledger_records, erase_account


class Command(BaseCommand):
    help = "Reaplica exclusões na base restaurada isolada; prévia por padrão. Nunca abra o banco antes deste procedimento."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            records = ledger_records()
            # Validate every signature before touching a restored account.
            count = 0
            for record in records:
                if get_user_model().objects.filter(pk=record["owner"]).exists():
                    count += 1
                    if options["apply"]:
                        get_user_model().objects.filter(pk=record["owner"]).update(
                            is_active=False
                        )
                        erase_account(
                            owner_id=record["owner"],
                            case_id=record["case"],
                            policy_reference=record["policy"],
                            apply=True,
                        )
                elif options["apply"]:
                    from accounts.privacy import delete_files

                    delete_files([record])
        except (ValidationError, ValueError, OSError) as exc:
            raise CommandError(
                "Reaplicação bloqueada: registro externo inválido ou indisponível."
            ) from exc
        self.stdout.write(
            json.dumps({"restored_accounts_marked": count, "apply": options["apply"]})
        )
