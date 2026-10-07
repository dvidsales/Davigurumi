"""Administrative erasure and external, signed tombstones. No public purge endpoint."""

import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.contrib.sessions.models import Session
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.http import HttpResponse
from django.utils import timezone

from .models import DemoWorkspace


def ledger_root():
    root = Path(settings.PRIVACY_LEDGER_DIR).resolve()
    if not settings.PRIVACY_LEDGER_KEY:
        raise ValidationError(
            "Configure uma chave separada para o registro de exclusões."
        )
    if not root.is_dir():
        raise ValidationError(
            "Registro externo de exclusões indisponível; operação bloqueada."
        )
    return root


def read_tombstone(owner_id):
    path = ledger_root() / (str(uuid.UUID(str(owner_id))) + ".json")
    if not path.exists():
        return None
    try:
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError()
        package = json.loads(path.read_text())
        record = signing.Signer(
            key=settings.PRIVACY_LEDGER_KEY, salt="erasure-v1"
        ).unsign_object(package["signed"])
        if (
            not isinstance(record, dict)
            or record.get("owner") != str(owner_id)
            or record.get("schema") != 1
            or not isinstance(record.get("files"), list)
            or not all(isinstance(name, str) for name in record["files"])
            or not isinstance(record.get("case"), str)
            or not isinstance(record.get("policy"), str)
        ):
            raise ValueError()
        return record
    except (ValueError, KeyError, signing.BadSignature, TypeError) as exc:
        raise ValidationError(
            "Registro de exclusão inválido; operação bloqueada."
        ) from exc


def assert_not_erased(owner_id):
    # A fresh local checkout has no ledger until its first erasure. Production must
    # mount the independent ledger and key, including for restoration and login.
    if (
        not settings.PRIVACY_LEDGER_REQUIRED
        and not Path(settings.PRIVACY_LEDGER_DIR).exists()
    ):
        return
    if read_tombstone(owner_id):
        raise ValidationError(
            "Conta marcada para exclusão; acesso e restauração bloqueados."
        )


def write_tombstone(record):
    root = ledger_root()
    target = root / (record["owner"] + ".json")
    value = signing.Signer(
        key=settings.PRIVACY_LEDGER_KEY, salt="erasure-v1"
    ).sign_object(record)
    fd, temporary = tempfile.mkstemp(dir=root, prefix=".erasure-")
    try:
        with os.fdopen(fd, "w") as file:
            json.dump({"signed": value}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def identities_for(owner_id):
    ids = [uuid.UUID(str(owner_id))]
    workspace = DemoWorkspace.objects.filter(owner_id=owner_id).first()
    if workspace:
        ids.append(workspace.demo_user_id)
    return ids


def inventory(owner_ids):
    from portability.archive import SCOPES

    result = {}
    for label, scope in SCOPES:
        result[label] = list(
            apps.get_model(label)
            .objects.filter(**{scope + "__in": owner_ids})
            .values_list("pk", flat=True)
        )
    result["portability.importjob"] = list(
        apps.get_model("portability.importjob")
        .objects.filter(owner_id__in=owner_ids)
        .values_list("pk", flat=True)
    )
    return result


def delete_files(records):
    root = Path(settings.MEDIA_ROOT).resolve()
    for record in records:
        for name in record["files"]:
            path = root / name
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or not path.resolve().is_relative_to(root)
            ):
                raise ValidationError(
                    "Arquivo de exclusão fora do armazenamento privado."
                )
            path.unlink(missing_ok=True)


@transaction.atomic
def erase_account(*, owner_id, case_id, policy_reference, apply=False):
    """Maintenance only: apply requires a suspended account and an approved policy.

    Tombstones are durable before deleting data. Failures block reactivation and
    may leave files for retry; never undo a tombstone to resume public operation.
    """
    case_id = str(uuid.UUID(str(case_id)))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", policy_reference):
        raise ValidationError("Referência de política inválida.")
    User = get_user_model()
    owner = User.objects.select_for_update().filter(pk=owner_id).first()
    if owner is None:
        record = read_tombstone(owner_id)
        if record and apply:
            delete_files([record])
            return {"already_erased": True}
        raise ValidationError("Conta não encontrada.")
    identities = identities_for(owner_id)
    rows = inventory(identities)
    assets = apps.get_model("sales.fileasset").objects.filter(owner_id__in=identities)
    result = {
        "identities": len(identities),
        "records": sum(map(len, rows.values())),
        "files": assets.count(),
        "apply": apply,
    }
    if not apply:
        return result
    if not settings.PRIVACY_LEDGER_REQUIRED:
        raise ValidationError(
            "Configure explicitamente o registro externo antes da exclusão."
        )
    if owner.is_active:
        raise ValidationError("Suspenda a conta antes de executar a exclusão.")
    from django.core.files.storage import default_storage, FileSystemStorage

    if not isinstance(default_storage, FileSystemStorage):
        raise ValidationError(
            "Este procedimento requer armazenamento privado local; adapte o expurgo ao provedor antes de excluir."
        )
    records = []
    for identity in identities:
        existing = read_tombstone(identity)
        filenames = set(assets.filter(owner_id=identity).values_list("file", flat=True))
        root = Path(settings.MEDIA_ROOT).resolve()
        upload_directory = root / "private" / str(identity)
        if upload_directory.exists():
            if not upload_directory.resolve().is_relative_to(root):
                raise ValidationError("Raiz de arquivos fora do armazenamento privado.")
            for path in upload_directory.rglob("*"):
                if path.is_file():
                    name = path.relative_to(root).as_posix()
                    # Include orphaned uploads from interrupted writes, but never
                    # delete a file referenced by another account.
                    if (
                        not apps.get_model("sales.fileasset")
                        .objects.filter(file=name)
                        .exclude(owner_id__in=identities)
                        .exists()
                    ):
                        filenames.add(name)
        record = existing or {
            "schema": 1,
            "owner": str(identity),
            "case": case_id,
            "policy": policy_reference,
            "created_at": timezone.now().isoformat(),
            "files": sorted(filenames),
        }
        # Validate storage paths before deleting database records.
        root = Path(settings.MEDIA_ROOT).resolve()
        for name in record["files"]:
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or not (root / name).resolve().is_relative_to(root)
            ):
                raise ValidationError("Caminho de exclusão fora da raiz privada.")
        write_tombstone(record)
        records.append(record)
    # Maintenance role only. PostgreSQL takes exclusive table locks; concurrent
    # writers wait until commit and guards are restored inside the transaction.
    guards = [
        ("sales_quoteitem", "quote_item_immutable"),
        ("sales_quoteimage", "image_owner_and_immutability"),
        ("materials_stockmovement", "compensation_integrity"),
        ("production_actualexpense", "expense_integrity"),
    ]
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for table, guard in guards:
                cursor.execute(f'ALTER TABLE "{table}" DISABLE TRIGGER "{guard}"')
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        elif connection.vendor == "sqlite":
            cursor.execute("PRAGMA defer_foreign_keys = ON")
        else:
            raise ValidationError("Banco não suportado pelo procedimento de exclusão.")
        for label, ids in reversed(list(rows.items())):
            model = apps.get_model(label)
            for offset in range(0, len(ids), 200):
                batch = ids[offset : offset + 200]
                placeholders = ",".join(["%s"] * len(batch))
                cursor.execute(
                    f"DELETE FROM {connection.ops.quote_name(model._meta.db_table)} WHERE {connection.ops.quote_name(model._meta.pk.column)} IN ({placeholders})",  # nosec B608: identifiers are fixed app metadata; every ID is bound separately.
                    [model._meta.pk.get_db_prep_value(pk, connection) for pk in batch],
                )
        DemoWorkspace.objects.filter(owner_id=owner_id).delete()
        # Sessions have no foreign key. Decode them using Django rather than
        # searching the signed/encoded text; never log their content.
        for session in Session.objects.iterator(chunk_size=200):
            if session.get_decoded().get("_auth_user_id") in set(map(str, identities)):
                session.delete()
        for identity in identities:
            # M2M auth memberships cascade through Django after domain deletion.
            User.objects.get(pk=identity).delete()
        if connection.vendor == "postgresql":
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for table, guard in guards:
                cursor.execute(f'ALTER TABLE "{table}" ENABLE TRIGGER "{guard}"')
    connection.check_constraints()
    transaction.on_commit(lambda: delete_files(records))
    return result


class ErasureGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                assert_not_erased(request.user.pk)
            except (ValidationError, OSError):
                logout(request)
                return HttpResponse(
                    "Acesso indisponível. Consulte o responsável pelo ambiente.",
                    status=403,
                )
        return self.get_response(request)
