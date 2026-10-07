import tempfile
import uuid
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction, IntegrityError
from django.http import Http404
from django.test import TestCase, override_settings
from production import tests as fixtures
from production.services import record_expense
from portability.archive import export_archive, import_archive
from accounts.demo import create_demo
from accounts.privacy import erase_account, read_tombstone, write_tombstone
from sales.services import make_token, get_token
from materials.models import Material


class ErasureTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "ledger").mkdir()
        (self.root / "media").mkdir()
        self.override = override_settings(
            PRIVACY_LEDGER_REQUIRED=True,
            PRIVACY_LEDGER_DIR=self.root / "ledger",
            PRIVACY_LEDGER_KEY="synthetic-ledger-key-87",
            MEDIA_ROOT=self.root / "media",
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        fixtures.ProductionTests.setUp(self)
        self.version.refresh_from_db()
        self.case = uuid.uuid4()

    def erase(self, apply=False):
        return erase_account(
            owner_id=self.owner.pk,
            case_id=self.case,
            policy_reference="synthetic-policy-v1",
            apply=apply,
        )

    def test_preview_does_not_change_accounts_or_create_tombstones(self):
        result = self.erase()
        self.assertGreater(result["records"], 10)
        self.assertIsNone(read_tombstone(self.owner.pk))
        self.assertTrue(get_user_model().objects.get(pk=self.owner.pk).is_active)
        with self.assertRaises(ValidationError):
            self.erase(apply=True)
        self.assertTrue(Material.objects.filter(pk=self.material.pk).exists())

    def test_complete_erasure_preserves_other_owner_and_rejects_old_archive(self):
        from decimal import Decimal
        from django.utils import timezone

        workspace = create_demo(self.owner)
        other = get_user_model().objects.create_user(
            username="retained", email="retained@example.test"
        )
        Material.objects.create(owner=other, name="Retained", kind="yarn", unit="g")
        package = export_archive(self.owner)
        record_expense(
            owner=self.owner,
            order_id=self.order.pk,
            amount=Decimal("5"),
            date=timezone.localdate(),
            description="Sensitive",
            key=uuid.uuid4(),
        )
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.captureOnCommitCallbacks(execute=True):
            self.erase(apply=True)
        self.assertFalse(
            get_user_model()
            .objects.filter(pk__in=[self.owner.pk, workspace.demo_user_id])
            .exists()
        )
        self.assertEqual(Material.objects.filter(owner=other).count(), 1)
        self.assertIsNotNone(read_tombstone(workspace.demo_user_id))
        with self.assertRaises(ValidationError):
            import_archive(owner=other, package=package)
        self.assertTrue(self.erase(apply=True)["already_erased"])
        # Transactional maintenance must re-enable every guard afterwards.
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_trigger WHERE tgname IN ('quote_item_immutable','image_owner_and_immutability','compensation_integrity','expense_integrity') AND tgenabled != 'O'"
                )
                self.assertEqual(cursor.fetchone()[0], 0)

    def test_restored_active_account_and_portal_blocked_by_tombstone(self):
        raw = make_token(self.version)
        self.client.force_login(self.owner)
        write_tombstone(
            {
                "schema": 1,
                "owner": str(self.owner.pk),
                "case": str(self.case),
                "policy": "synthetic",
                "files": [],
            }
        )
        self.assertEqual(self.client.get("/").status_code, 403)
        with self.assertRaises(Http404):
            get_token(raw)
        with self.assertRaises(ValidationError):
            export_archive(self.owner)

    def test_file_erasure_and_corrupt_ledger_fail_closed(self):
        from sales.models import FileAsset

        asset = FileAsset.objects.create(
            owner=self.owner,
            file="private/synthetic.png",
            label="Sensitive",
            sha256="0" * 64,
            size=3,
            width=1,
            height=1,
        )
        (self.root / "media" / "private").mkdir()
        path = self.root / "media" / asset.file.name
        path.write_bytes(b"abc")
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.captureOnCommitCallbacks(execute=True):
            self.erase(apply=True)
        self.assertFalse(path.exists())
        (self.root / "ledger" / (str(self.owner.pk) + ".json")).write_text("{}")
        with self.assertRaises(ValidationError):
            read_tombstone(self.owner.pk)

    def test_reapply_dry_run_then_erases_restored_data(self):
        from django.core.management import call_command
        import io

        write_tombstone(
            {
                "schema": 1,
                "owner": str(self.owner.pk),
                "case": str(self.case),
                "policy": "synthetic",
                "files": [],
            }
        )
        call_command("reapply_erasure", stdout=io.StringIO())
        self.assertTrue(get_user_model().objects.filter(pk=self.owner.pk).exists())
        call_command("reapply_erasure", apply=True, stdout=io.StringIO())
        self.assertFalse(get_user_model().objects.filter(pk=self.owner.pk).exists())

    @override_settings(PRIVACY_LEDGER_REQUIRED=True, PRIVACY_LEDGER_KEY="")
    def test_production_missing_ledger_key_blocks_session_and_portal(self):
        self.client.force_login(self.owner)
        raw = make_token(self.version)
        self.assertEqual(self.client.get("/").status_code, 403)
        with self.assertRaises(Http404):
            get_token(raw)

    def test_corrupt_tombstone_blocks_session_and_portal(self):
        self.client.force_login(self.owner)
        raw = make_token(self.version)
        (self.root / "ledger" / (str(self.owner.pk) + ".json")).write_text(
            '{"signed":"invalid"}'
        )
        self.assertEqual(self.client.get("/").status_code, 403)
        with self.assertRaises(Http404):
            get_token(raw)

    def test_pending_mail_is_not_sent_after_erasure_or_opt_out(self):
        from unittest.mock import patch
        from operations.models import NotificationPreference, Notification, OutboxEvent
        from operations.services import deliver_outbox

        NotificationPreference.objects.create(owner=self.owner, email_enabled=True)
        notification = Notification.objects.create(
            owner=self.owner, key="synthetic", message="Personal details"
        )
        row = OutboxEvent.objects.create(notification=notification)
        write_tombstone(
            {
                "schema": 1,
                "owner": str(self.owner.pk),
                "case": str(self.case),
                "policy": "synthetic",
                "files": [],
            }
        )
        with patch("operations.services.send_mail") as sender:
            deliver_outbox()
            sender.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.last_error, "PrivacyBlocked")

    def test_orphan_upload_removed_but_another_accounts_file_is_preserved(self):
        from sales.models import FileAsset

        directory = self.root / "media" / "private" / str(self.owner.pk)
        directory.mkdir(parents=True)
        orphan = directory / "orphan.png"
        shared = directory / "other-owned.png"
        orphan.write_bytes(b"orphan")
        shared.write_bytes(b"other")
        other = get_user_model().objects.create_user(
            username="other_files", email="other_files@example.test"
        )
        FileAsset.objects.create(
            owner=other,
            file=shared.relative_to(self.root / "media").as_posix(),
            label="Other",
            sha256="0" * 64,
            size=5,
            width=1,
            height=1,
        )
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.captureOnCommitCallbacks(execute=True):
            self.erase(apply=True)
        self.assertFalse(orphan.exists())
        self.assertTrue(shared.exists())
