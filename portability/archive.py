"""Versioned, signed relational archive. Restores only into an empty destination.

Authentication/session/secret values are never part of an export. Imported approvals
remain historical metadata; they cannot authorize creation of a new order.
"""

import base64
import hashlib
import json
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers, signing
from django.core.exceptions import ValidationError
from django.core.management.color import no_style
from django.db import connection, transaction, models, IntegrityError, DataError
from django.utils import timezone
from django.utils.crypto import constant_time_compare

MAX_RECORDS = 10000
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024

SCOPES = [
    ("materials.material", "owner"),
    ("materials.materialconversion", "material__owner"),
    ("materials.costlayer", "material__owner"),
    ("materials.stockoperation", "owner"),
    ("materials.stockmovement", "material__owner"),
    ("materials.stockreservation", "layer__material__owner"),
    ("materials.reservationevent", "reservation__layer__material__owner"),
    ("purchasing.supplier", "owner"),
    ("purchasing.purchase", "owner"),
    ("purchasing.purchaseitem", "purchase__owner"),
    ("purchasing.receipt", "purchase__owner"),
    ("purchasing.receiptline", "receipt__purchase__owner"),
    ("projects.project", "owner"),
    ("projects.projectrevision", "project__owner"),
    ("projects.projectmaterial", "revision__project__owner"),
    ("projects.materialalternative", "line__revision__project__owner"),
    ("sales.client", "owner"),
    ("sales.quote", "owner"),
    ("sales.quoteversion", "quote__owner"),
    ("sales.quoteitem", "version__quote__owner"),
    ("sales.fileasset", "owner"),
    ("sales.quoteimage", "version__quote__owner"),
    ("sales.sharetoken", "version__quote__owner"),
    ("sales.quoteevent", "version__quote__owner"),
    ("production.order", "owner"),
    ("production.orderitem", "order__owner"),
    ("production.consumption", "item__order__owner"),
    ("production.productionsession", "owner"),
    ("production.sessioncorrection", "session__owner"),
    ("production.deliveryevent", "item__order__owner"),
    ("production.actualexpense", "order__owner"),
    ("finance.payment", "owner"),
    ("finance.paymentallocation", "payment__owner"),
    ("finance.refund", "allocation__payment__owner"),
    ("finance.receivable", "order__owner"),
    ("operations.notificationpreference", "owner"),
    ("operations.notification", "owner"),
    ("operations.auditevent", "owner"),
    ("operations.outboxevent", "notification__owner"),
]


def canonical(payload):
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


@transaction.atomic
def export_archive(owner):
    from accounts.privacy import assert_not_erased

    assert_not_erased(owner.pk)
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    records = []
    files = {}
    byte_budget = 2048
    for label, scope in SCOPES:
        model = apps.get_model(label)
        for obj in (
            model.objects.filter(**{scope: owner})
            .order_by("pk")
            .iterator(chunk_size=200)
        ):
            if len(records) >= MAX_RECORDS:
                raise ValidationError(
                    "Limite de 10000 registros por pacote. A exportação não trunca o histórico."
                )
            record = json.loads(serializers.serialize("json", [obj]))[0]
            byte_budget += len(canonical(record).encode("utf-8")) + 2
            if byte_budget > MAX_ARCHIVE_BYTES:
                raise ValidationError(
                    "O pacote excede 50 MB. A exportação não trunca o histórico."
                )
            records.append(record)
    from sales.models import FileAsset

    for asset in FileAsset.objects.filter(owner=owner):
        with asset.file.open("rb") as uploaded:
            raw = uploaded.read(5 * 1024 * 1024 + 1)
        if hashlib.sha256(raw).hexdigest() != asset.sha256:
            raise ValidationError(
                "Arquivo privado diverge do hash registrado. Verifique o armazenamento antes de exportar."
            )
        if len(raw) > 5 * 1024 * 1024 or len(raw) != asset.size:
            raise ValidationError("Tamanho do arquivo privado incompatível.")
        byte_budget += (
            ((len(raw) + 2) // 3) * 4 + len(asset.file.name.encode("utf-8")) + 256
        )
        if byte_budget > MAX_ARCHIVE_BYTES:
            raise ValidationError(
                "O pacote excede 50 MB. A exportação não trunca o histórico."
            )
        files[asset.file.name] = {
            "sha256": asset.sha256,
            "bytes": base64.b64encode(raw).decode(),
        }
    payload = {
        "schema": 1,
        "created_at": timezone.now().isoformat(),
        "source_owner": str(owner.pk),
        "records": records,
        "files": files,
    }
    return {
        "payload": payload,
        "signature": signing.Signer(salt="davigurumi-archive-v1").signature(
            canonical(payload)
        ),
    }


def validate_archive(package):
    if (
        not isinstance(package, dict)
        or set(package) != {"payload", "signature"}
        or not isinstance(package["signature"], str)
    ):
        raise ValidationError("Estrutura de pacote inválida.")
    payload = package["payload"]
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValidationError("Versão de pacote não suportada.")
    if not constant_time_compare(
        signing.Signer(salt="davigurumi-archive-v1").signature(canonical(payload)),
        package["signature"],
    ):
        raise ValidationError(
            "Assinatura de origem inválida. Pacotes deste protótipo só são restaurados com a chave original do ambiente."
        )
    records = payload.get("records", [])
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValidationError("Limite de 10000 registros por pacote.")
    allowed = {label for label, _ in SCOPES}
    seen = set()
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"model", "pk", "fields"}
            or not isinstance(record["model"], str)
            or record["model"] not in allowed
            or not isinstance(record["fields"], dict)
        ):
            raise ValidationError("Modelo/estrutura não permitido no pacote.")
        key = (record["model"], str(record["pk"]))
        if key in seen:
            raise ValidationError("ID duplicado no pacote.")
        seen.add(key)
        fields = {
            field.name for field in apps.get_model(record["model"])._meta.local_fields
        }
        if not set(record["fields"]).issubset(fields):
            raise ValidationError("Campo não permitido no pacote.")
    for record in records:
        for field in apps.get_model(record["model"])._meta.local_fields:
            if field.is_relation and field.related_model != get_user_model():
                target = record["fields"].get(field.name)
                if (
                    target is not None
                    and (field.related_model._meta.label_lower, str(target)) not in seen
                ):
                    raise ValidationError(
                        "Relação ausente no pacote. A restauração não pode usar registros de outra conta."
                    )
    if not isinstance(payload.get("files", {}), dict):
        raise ValidationError("Estrutura de arquivos inválida.")
    for name, file in payload.get("files", {}).items():
        if (
            not isinstance(name, str)
            or not isinstance(file, dict)
            or set(file) != {"bytes", "sha256"}
            or not isinstance(file["sha256"], str)
            or not isinstance(file["bytes"], str)
        ):
            raise ValidationError("Estrutura de arquivo inválida.")
        if len(file["bytes"]) > ((5 * 1024 * 1024 + 2) // 3) * 4:
            raise ValidationError("Arquivo codificado excede o limite.")
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValidationError("Caminho de arquivo inválido.")
        try:
            raw = base64.b64decode(file["bytes"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValidationError("Arquivo codificado inválido.") from exc
        if (
            len(raw) > 5 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != file["sha256"]
        ):
            raise ValidationError("Tamanho ou hash de arquivo incompatível.")
    assets = {
        record["fields"]["file"]: record["fields"]["sha256"]
        for record in records
        if record["model"] == "sales.fileasset"
    }
    if set(assets) != set(payload.get("files", {})) or any(
        payload["files"][name]["sha256"] != sha for name, sha in assets.items()
    ):
        raise ValidationError("Os arquivos não correspondem aos registros de imagens.")
    return payload


@transaction.atomic
def import_archive(*, owner, package):
    payload = validate_archive(package)
    from accounts.privacy import assert_not_erased

    try:
        assert_not_erased(payload["source_owner"])
        assert_not_erased(owner.pk)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValidationError("Identidade de origem inválida.") from exc
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    for label, scope in SCOPES:
        if label == "operations.notificationpreference":
            continue
        if apps.get_model(label).objects.filter(**{scope: owner}).exists():
            raise ValidationError(
                "Restaure em uma conta vazia. Não sobrescrevemos registros existentes."
            )
    records = json.loads(json.dumps(payload["records"]))
    for record in records:
        if apps.get_model(record["model"]).objects.filter(pk=record["pk"]).exists():
            raise ValidationError(
                "Há colisão de IDs nesta instalação. Use uma base vazia para preservar as relações originais."
            )
    from collections import Counter
    from accounts.quotas import ensure_capacity, ensure_storage

    counts = Counter(record["model"] for record in records)
    for label, count in counts.items():
        if label in settings.ACCOUNT_RECORD_LIMITS:
            ensure_capacity(owner, label, additional=count)
    storage_bytes = sum(
        int(record["fields"]["size"])
        for record in records
        if record["model"] == "sales.fileasset"
    )
    storage_bytes += sum(
        len(base64.b64decode(record["fields"].get("pdf", "")))
        for record in records
        if record["model"] == "sales.quoteversion"
    )
    ensure_storage(owner, storage_bytes)
    staged = {}
    created_paths = []
    from django.core.files.storage import default_storage

    root = Path(settings.MEDIA_ROOT).resolve()
    try:
        if any(
            record["model"] == "operations.notificationpreference" for record in records
        ):
            apps.get_model("operations.notificationpreference").objects.filter(
                owner=owner
            ).delete()
        for label, _ in SCOPES:
            group = [record for record in records if record["model"] == label]
            if label == "production.actualexpense":
                group.sort(key=lambda record: bool(record["fields"].get("reverses")))
            if label == "materials.stockmovement":
                group.sort(key=lambda record: bool(record["fields"].get("reverses")))
            if label == "sales.quoteversion":
                group.sort(key=lambda record: record["fields"]["number"])
            for record in group:
                model = apps.get_model(label)
                for field in model._meta.local_fields:
                    if field.is_relation and field.related_model == get_user_model():
                        record["fields"][field.name] = str(owner.pk)
                values = record["fields"]
                if label == "projects.project":
                    staged[(label, str(record["pk"]))] = {
                        "current_revision": values.get("current_revision")
                    }
                    values["current_revision"] = None
                if label == "sales.quote":
                    staged[(label, str(record["pk"]))] = {
                        "current_version": values.get("current_version")
                    }
                    values["current_version"] = None
                if label == "sales.quoteversion":
                    staged[(label, str(record["pk"]))] = values.copy()
                    values.update(
                        {
                            "published_at": None,
                            "status": "draft",
                            "approval_origin": "imported",
                        }
                    )
                if label == "sales.sharetoken":
                    values["revoked_at"] = timezone.now().isoformat()
                if label == "operations.notificationpreference":
                    values["email_enabled"] = False
                if label == "operations.outboxevent" and values["status"] == "pending":
                    values["status"] = "imported"
            for obj in serializers.deserialize(
                "json", json.dumps(group), handle_forward_references=True
            ):
                obj.save()
        for (label, pk), values in staged.items():
            if label == "sales.quoteversion":
                values["approval_origin"] = "imported"
            model = apps.get_model(label)
            typed = {}
            for name, value in values.items():
                field = model._meta.get_field(name)
                typed[name] = (
                    base64.b64decode(value)
                    if isinstance(field, models.BinaryField)
                    else (value if field.is_relation else field.to_python(value))
                )
            model.objects.filter(pk=pk).update(**typed)
        for statement in connection.ops.sequence_reset_sql(
            no_style(), [apps.get_model(label) for label, _ in SCOPES]
        ):
            with connection.cursor() as cursor:
                cursor.execute(statement)
        for name, file in payload.get("files", {}).items():
            destination = root / name
            if not destination.resolve().is_relative_to(root):
                raise ValidationError("Caminho de armazenamento inválido.")
            if default_storage.exists(name):
                raise ValidationError(
                    "Arquivo de destino já existe. Restaure em armazenamento vazio."
                )
            from django.core.files.base import ContentFile

            saved = default_storage.save(
                name, ContentFile(base64.b64decode(file["bytes"]))
            )
            created_paths.append(saved)
            if saved != name:
                raise ValidationError("Arquivo de destino mudou durante a restauração.")
        connection.check_constraints()
    except Exception as exc:
        for name in created_paths:
            default_storage.delete(name)
        if isinstance(
            exc, (IntegrityError, DataError, serializers.base.DeserializationError)
        ):
            raise ValidationError(
                "O pacote não é compatível com as restrições desta base; nenhum registro foi restaurado."
            ) from exc
        raise
    return len(records)
