import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from materials.forms import MaterialForm
from materials.services import create_material
from materials.models import Material
from portability.tables import preview_import, confirm_import
from sales.services import create_quote, publish
from production import tests as fixtures
from accounts.quotas import ensure_storage


class QuotaTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="quota", email="quota@example.test"
        )

    @override_settings(ACCOUNT_RECORD_LIMITS={"materials.material": 1})
    def test_material_repeat_succeeds_at_limit_new_one_rejected(self):
        form = MaterialForm(
            {
                "name": "Fio",
                "kind": "yarn",
                "unit": "g",
                "initial_quantity": "0",
                "request_key": uuid.uuid4(),
                "minimum_stock": "0",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        first = create_material(owner=self.owner, form=form)
        self.assertEqual(create_material(owner=self.owner, form=form).pk, first.pk)
        other = MaterialForm(
            {**form.data, "request_key": uuid.uuid4(), "name": "Segundo"}
        )
        self.assertTrue(other.is_valid(), other.errors)
        with self.assertRaises(ValidationError):
            create_material(owner=self.owner, form=other)
        self.assertEqual(Material.objects.filter(owner=self.owner).count(), 1)

    @override_settings(ACCOUNT_RECORD_LIMITS={"materials.material": 1})
    def test_bulk_import_is_atomic_at_limit(self):
        upload = SimpleUploadedFile(
            "two.csv",
            b"nome;tipo;unidade;quantidade;custo_unitario\nUm;fio;g;0;\nDois;fio;g;0;\n",
        )
        job = preview_import(
            owner=self.owner,
            upload=upload,
            mapping={
                column: column
                for column in __import__(
                    "portability.tables", fromlist=["COLUMNS"]
                ).COLUMNS
            },
            locale="pt-br",
        )
        self.assertFalse(job.errors, job.errors)
        with self.assertRaises(ValidationError):
            confirm_import(owner=self.owner, job_id=job.pk)
        self.assertFalse(Material.objects.filter(owner=self.owner).exists())
        job.refresh_from_db()
        self.assertIsNone(job.applied_at)

    @override_settings(
        ACCOUNT_RECORD_LIMITS={
            "sales.quote": 0,
            "sales.client": 0,
            "purchasing.purchase": 0,
            "purchasing.supplier": 0,
        }
    )
    def test_form_limits_return_errors_not_server_failure(self):
        self.client.force_login(self.owner)
        from django.urls import reverse

        for path, data in [
            (reverse("sales:create"), {"valid_days": 15}),
            (reverse("sales:clients"), {"name": "Private"}),
            (
                reverse("purchasing:create"),
                {"date": "2026-10-07", "freight": "0", "discount": "0"},
            ),
            (reverse("purchasing:suppliers"), {"name": "Private"}),
        ]:
            response = self.client.post(path, data)
            self.assertEqual(response.status_code, 200, path)
            self.assertContains(response, "Limite de registros")

    @override_settings(ACCOUNT_STORAGE_LIMIT=1)
    def test_pdf_and_images_count_towards_storage_limit(self):
        from sales.models import QuoteVersion, FileAsset

        quote = create_quote(owner=self.owner)
        QuoteVersion.objects.filter(quote=quote).update(pdf=b"123")
        with self.assertRaises(ValidationError):
            ensure_storage(self.owner, 0)
