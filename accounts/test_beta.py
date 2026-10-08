import json
import uuid
from io import BytesIO
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, TransactionTestCase, SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image
from accounts.invites import invite_code
from accounts.privacy import (
    read_tombstone,
    write_tombstone,
    assert_not_erased,
    erase_account,
)
from config.storage import SupabasePrivateStorage
from sales.files import attach_image
from sales.services import create_quote
from portability.archive import export_archive, import_archive


class MemorySupabase:
    def __init__(self):
        self.objects = {}

    def request(self, storage, method, path, data=None, missing=False, upsert=False):
        parts = path.strip("/").split("/")
        if parts[0] == "bucket":
            return json.dumps({"id": parts[1], "public": False}).encode()
        if parts[:2] == ["object", "list"]:
            bucket = parts[2]
            prefix = (data["prefix"].rstrip("/") + "/") if data["prefix"] else ""
            values = {}
            for b, name in self.objects:
                if b == bucket and name.startswith(prefix):
                    rest = name[len(prefix) :]
                    name = rest.split("/")[0]
                    values[name] = {
                        "name": name,
                        "id": None if "/" in rest else "synthetic",
                    }
            return json.dumps(
                list(values.values())[data["offset"] : data["offset"] + data["limit"]]
            ).encode()
        if parts[:2] == ["object", "authenticated"]:
            key = (parts[2], "/".join(parts[3:]))
            if key not in self.objects:
                raise FileNotFoundError
            return self.objects[key]
        if parts[0] == "object" and method == "POST":
            key = (parts[1], "/".join(parts[2:]))
            if key in self.objects and not upsert:
                raise ValidationError("Objeto já existe.")
            self.objects[key] = data
            return b"{}"
        if parts[0] == "object" and method == "DELETE":
            for name in data["prefixes"]:
                self.objects.pop((parts[1], name), None)
            return b"{}"
        raise AssertionError((method, path))


@override_settings(
    BETA_MODE=True,
    PUBLIC_SIGNUP_ENABLED=False,
    BETA_INVITE_SECRET="synthetic-invitation-master-secret",
    BETA_EMAILS={"tester@example.test"},
)
class BetaInvitationTests(TestCase):
    def test_only_allowlisted_email_with_matching_invite_can_register(self):
        data = {
            "username": "tester",
            "email": "tester@example.test",
            "password1": "Synthetic-Test-Password-923!",
            "password2": "Synthetic-Test-Password-923!",
        }
        self.assertEqual(self.client.post(reverse("signup"), data).status_code, 200)
        self.assertFalse(get_user_model().objects.exists())
        data["invite_code"] = invite_code(settings.BETA_INVITE_SECRET, data["email"])
        response = self.client.post(reverse("signup"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.client.logout()
        data.update(username="foreign", email="foreign@example.test")
        self.assertEqual(self.client.post(reverse("signup"), data).status_code, 200)
        self.assertEqual(get_user_model().objects.count(), 1)


@override_settings(
    REMOTE_PRIVATE_STORAGE=True,
    SUPABASE_URL="https://synthetic.supabase.co",
    SUPABASE_SERVICE_KEY="synthetic-key",
    SUPABASE_FILES_BUCKET="private-files",
    SUPABASE_LEDGER_BUCKET="private-ledger",
    PRIVACY_LEDGER_REQUIRED=True,
    PRIVACY_LEDGER_KEY="independent-synthetic-ledger-key",
    STORAGES={
        "default": {"BACKEND": "config.storage.SupabasePrivateStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class RemotePrivateStorageTests(TransactionTestCase):
    def setUp(self):
        self.memory = MemorySupabase()
        memory = self.memory
        self.patch = patch.object(
            SupabasePrivateStorage,
            "request",
            lambda storage, *args, **kwargs: memory.request(storage, *args, **kwargs),
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.owner = get_user_model().objects.create_user(
            username="cloud_test", email="cloud@example.test"
        )

    def test_storage_is_private_and_paths_cannot_escape(self):
        name = default_storage.save("private/test.jpg", ContentFile(b"image"))
        with default_storage.open(name) as file:
            self.assertEqual(file.read(), b"image")
        self.assertEqual(default_storage.size(name), 5)
        with self.assertRaises(ValueError):
            default_storage.url(name)
        for bad in ("../file", "/absolute", "x\\y", "a//b"):
            with self.assertRaises(ValidationError):
                default_storage.open(bad)
        default_storage.delete(name)
        self.assertFalse(default_storage.exists(name))

    def test_remote_archive_restores_images_without_using_local_disk(self):
        quote = create_quote(owner=self.owner)
        image = BytesIO()
        Image.new("RGB", (8, 8), "green").save(image, format="PNG")
        from django.core.files.uploadedfile import SimpleUploadedFile

        link = attach_image(
            owner=self.owner,
            version_id=quote.versions.get().pk,
            upload=SimpleUploadedFile("x.png", image.getvalue()),
            label="Privada",
        )
        archive = export_archive(self.owner)
        from django.core.management import call_command

        call_command("flush", verbosity=0, interactive=False)
        other = get_user_model().objects.create_user(
            username="restored_cloud", email="restored@example.test"
        )
        self.memory.objects.clear()  # Simulates a distinct empty destination bucket.
        import_archive(owner=other, package=archive)
        from sales.models import FileAsset

        restored = FileAsset.objects.get(owner=other)
        with restored.file.open() as f:
            self.assertEqual(
                __import__("hashlib").sha256(f.read()).hexdigest(), restored.sha256
            )
        self.assertTrue(default_storage.exists(link.asset.file.name))

    def test_owner_image_outage_is_safe_and_foreign_owner_still_denied(self):
        from sales.models import FileAsset
        from django.db.models.fields.files import FieldFile

        asset = FileAsset.objects.create(
            owner=self.owner,
            file="private/synthetic.jpg",
            sha256="0" * 64,
            size=1,
            width=1,
            height=1,
        )
        self.client.force_login(self.owner)
        with patch.object(
            FieldFile, "open", side_effect=ValidationError("provider credential hidden")
        ):
            response = self.client.get(reverse("sales:owner_image", args=[asset.pk]))
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, "credential", status_code=503)
            other = get_user_model().objects.create_user(username="other_image_cloud")
            self.client.force_login(other)
            self.assertEqual(
                self.client.get(
                    reverse("sales:owner_image", args=[asset.pk])
                ).status_code,
                404,
            )

    def test_remote_signed_ledger_blocks_access_and_deletion_removes_orphans(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        name = "private/" + str(self.owner.pk) + "/orphan.jpg"
        default_storage.save(name, ContentFile(b"orphan"))
        result = erase_account(
            owner_id=self.owner.pk,
            case_id=uuid.uuid4(),
            policy_reference="synthetic-policy",
            apply=True,
        )
        self.assertTrue(result["apply"])
        record = read_tombstone(self.owner.pk)
        self.assertIn(name, record["files"])
        self.assertFalse(default_storage.exists(name))
        with self.assertRaises(ValidationError):
            assert_not_erased(self.owner.pk)
        self.memory.objects[
            (settings.SUPABASE_LEDGER_BUCKET, str(self.owner.pk) + ".json")
        ] = b'{"signed":"tampered"}'
        with self.assertRaises(ValidationError):
            read_tombstone(self.owner.pk)

    def test_provider_outage_fails_closed_and_public_bucket_is_rejected(self):
        with patch.object(
            SupabasePrivateStorage,
            "request",
            side_effect=ValidationError("Unavailable"),
        ):
            with self.assertRaises(ValidationError):
                assert_not_erased(self.owner.pk)
        with patch.object(
            SupabasePrivateStorage, "request", return_value=b'{"public":true}'
        ):
            with self.assertRaises(ValidationError):
                SupabasePrivateStorage().check_private()


class ProxyAndHealthTests(TestCase):
    def test_forwarded_ip_not_trusted_by_default_and_trusted_proxy_uses_last_ip(self):
        from accounts.models import AuthThrottle

        for setting, expected in ((False, 1), (True, 2)):
            AuthThrottle.objects.all().delete()
            with override_settings(TRUSTED_PROXY=setting):
                for ip in ("192.0.2.1", "192.0.2.2"):
                    self.client.post(
                        reverse("login"),
                        {},
                        REMOTE_ADDR="127.0.0.1",
                        HTTP_X_FORWARDED_FOR="forged, " + ip,
                    )
            self.assertEqual(AuthThrottle.objects.count(), expected)

    def test_health_does_not_expose_database_details(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})
        from django.db.utils import OperationalError

        with patch(
            "config.health.connection.cursor",
            side_effect=OperationalError("secret details"),
        ):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "secret", status_code=503)


class ReviewFormTests(SimpleTestCase):
    def test_unconfirmed_payment_cannot_block_production(self):
        from production.forms import CompletionForm

        form = CompletionForm(
            {
                "state": "synthetic",
                "complete": "on",
                "key": str(uuid.uuid4()),
                "amount": "invalid",
                "date": "invalid",
                "method": "invalid",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["receive_payment"])
        self.assertIsNone(form.cleaned_data["amount"])
        confirmed = CompletionForm(
            {
                "state": "synthetic",
                "receive_payment": "on",
                "key": str(uuid.uuid4()),
                "amount": "invalid",
                "date": "invalid",
                "method": "invalid",
            }
        )
        self.assertFalse(confirmed.is_valid())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend")
    def test_missing_email_service_does_not_promise_reset_email(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "pessoa que convidou", status_code=503)
