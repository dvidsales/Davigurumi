import copy, tempfile, uuid
from decimal import Decimal
from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from PIL import Image
from materials.models import Material
from materials.stock import receive_stock
from .tables import (
    COLUMNS,
    preview_import,
    confirm_import,
    read_table,
    export_material_rows,
)
from .archive import export_archive, validate_archive, import_archive


class TableTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="importer", email="importer@example.test"
        )

    def preview(self, text):
        return preview_import(
            owner=self.owner,
            upload=SimpleUploadedFile("materials.csv", text.encode()),
            mapping={key: key for key in COLUMNS},
            locale="pt-br",
        )

    def test_preview_is_not_a_write_and_confirmation_is_idempotent(self):
        job = self.preview(
            "nome;tipo;unidade;quantidade;custo_unitario\nFio azul;fio;g;508;0,10\nBotão;acessorio;un;4;\n"
        )
        self.assertFalse(job.errors)
        self.assertEqual(Material.objects.count(), 0)
        self.assertEqual(confirm_import(owner=self.owner, job_id=job.pk), 2)
        self.assertEqual(confirm_import(owner=self.owner, job_id=job.pk), 2)
        self.assertEqual(Material.objects.count(), 2)
        self.assertEqual(
            Material.objects.get(name="Fio azul").physical_stock, Decimal("508")
        )
        self.assertIsNone(Material.objects.get(name="Botão").layers.get().unit_cost)

    def test_one_bad_row_blocks_the_entire_import(self):
        job = self.preview(
            "nome;tipo;unidade;quantidade\nFio;fio;g;10\nBotão;acessorio;un;1,5\n"
        )
        self.assertEqual(len(job.errors), 1)
        with self.assertRaises(ValidationError):
            confirm_import(owner=self.owner, job_id=job.pk)
        self.assertFalse(Material.objects.exists())

    def test_duplicate_and_ambiguous_decimal_are_visible_errors(self):
        job = self.preview("nome;tipo;unidade;quantidade\nFio;fio;g;1.5\n")
        self.assertEqual(len(job.errors), 1)
        job = self.preview("nome;tipo;unidade;quantidade\nFio;fio;g;1\nFio;fio;g;2\n")
        self.assertEqual(len(job.errors), 1)

    def test_other_owner_cannot_confirm_or_read_preview(self):
        job = self.preview("nome;tipo;unidade\nFio;fio;g\n")
        other = get_user_model().objects.create_user(
            username="other", email="other@example.test"
        )
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(reverse("portability:preview", args=[job.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("portability:confirm", args=[job.pk])).status_code,
            404,
        )

    def test_xlsx_formula_rejected_and_numeric_cells_ignore_text_locale(self):
        workbook = Workbook()
        workbook.active.append(
            ["nome", "tipo", "unidade", "quantidade", "custo_unitario"]
        )
        workbook.active.append(["Fio", "fio", "g", 1.5, 0.1])
        output = BytesIO()
        workbook.save(output)
        job = preview_import(
            owner=self.owner,
            upload=SimpleUploadedFile("x.xlsx", output.getvalue()),
            mapping={key: key for key in COLUMNS},
            locale="pt-br",
        )
        self.assertFalse(job.errors)
        self.assertEqual(job.rows[0]["payload"]["initial_quantity"], "1.5")
        workbook.active["A2"] = "=1+1"
        output = BytesIO()
        workbook.save(output)
        with self.assertRaises(ValidationError):
            read_table(SimpleUploadedFile("x.xlsx", output.getvalue()))

    def test_export_neutralizes_formula_text(self):
        Material.objects.create(owner=self.owner, name="=1+1", kind="yarn", unit="g")
        self.assertEqual(export_material_rows(self.owner)[1][0], "'=1+1")

    def test_signature_tampering_and_existing_destination_are_rejected(self):
        material = Material.objects.create(
            owner=self.owner, name="Fio", kind="yarn", unit="g"
        )
        package = export_archive(self.owner)
        bad = copy.deepcopy(package)
        bad["payload"]["records"][0]["fields"]["name"] = "Alterado"
        with self.assertRaises(ValidationError):
            validate_archive(bad)
        with self.assertRaises(ValidationError):
            import_archive(owner=self.owner, package=package)
        self.assertEqual(Material.objects.get(pk=material.pk).name, "Fio")


class ArchiveRoundTripTests(TransactionTestCase):
    def test_complete_roundtrip_preserves_money_stock_pdf_relations_and_files(self):
        from pathlib import Path
        from projects.services import create_project, add_material
        from sales.services import create_quote, add_quote_item, publish, decide
        from sales.files import attach_image
        from sales.models import QuoteVersion, ShareToken, FileAsset
        from production.services import (
            create_order,
            reserve_order,
            consume_item,
            start_session,
            stop_session,
            apply_amendment,
        )
        from production.models import Order, Consumption
        from finance.services import record_payment
        from finance.models import Payment

        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            with override_settings(MEDIA_ROOT=source):
                owner = get_user_model().objects.create_user(
                    username="source", email="source@example.test"
                )
                material = Material.objects.create(
                    owner=owner, name="Fio", kind="yarn", unit="g"
                )
                receive_stock(
                    owner=owner,
                    material_id=material.pk,
                    quantity=Decimal("508"),
                    unit_cost=Decimal(".1"),
                    key=uuid.uuid4(),
                )
                project = create_project(
                    owner=owner,
                    name="Boneco",
                    estimated_seconds=3600,
                    hourly_rate=Decimal("30"),
                )
                add_material(
                    owner=owner,
                    project_id=project.pk,
                    material_id=material.pk,
                    quantity=Decimal("120"),
                )
                quote = create_quote(owner=owner)
                version = quote.versions.get()
                add_quote_item(
                    owner=owner,
                    version_id=version.pk,
                    project_id=project.pk,
                    quantity=1,
                )
                output = BytesIO()
                Image.new("RGB", (20, 20), "green").save(output, format="PNG")
                attach_image(
                    owner=owner,
                    version_id=version.pk,
                    upload=SimpleUploadedFile("image.png", output.getvalue()),
                    label="Peça",
                    is_public=True,
                )
                version, raw = publish(owner=owner, version_id=version.pk)
                original_pdf = bytes(version.pdf)
                decide(raw=raw, action="approve", key=uuid.uuid4(), declaration=True)
                order = create_order(owner=owner, version_id=version.pk)
                item = order.items.get()
                reserve_order(owner=owner, order_id=order.pk, key=uuid.uuid4())
                from materials.models import StockReservation

                reservation = StockReservation.objects.get(reference=item.pk)
                consume_item(
                    owner=owner,
                    item_id=item.pk,
                    material_id=material.pk,
                    quantity=Decimal("50"),
                    reservation_id=reservation.pk,
                    key=uuid.uuid4(),
                )
                record_payment(
                    owner=owner,
                    version_id=version.pk,
                    amount=Decimal("20"),
                    key=uuid.uuid4(),
                    method="pix",
                    date=timezone.localdate(),
                )
                session = start_session(owner=owner, item_id=item.pk)
                stop_session(owner=owner, session_id=session.pk)
                quote2 = create_quote(owner=owner)
                version2 = quote2.versions.get()
                add_quote_item(
                    owner=owner,
                    version_id=version2.pk,
                    project_id=project.pk,
                    quantity=1,
                )
                _, raw2 = publish(owner=owner, version_id=version2.pk)
                decide(raw=raw2, action="approve", key=uuid.uuid4(), declaration=True)
                from sales.services import new_version

                amendment = new_version(owner=owner, quote_id=quote.pk)
                _, amendment_raw = publish(owner=owner, version_id=amendment.pk)
                decide(
                    raw=amendment_raw,
                    action="approve",
                    key=uuid.uuid4(),
                    declaration=True,
                )
                from production.services import record_expense
                from materials.stock import compensate_movement
                spent=record_expense(owner=owner,order_id=order.pk,amount=Decimal("10"),date=timezone.localdate(),description="Envio",key=uuid.uuid4())
                record_expense(owner=owner,order_id=order.pk,amount=Decimal("10"),date=timezone.localdate(),description="Correção",key=uuid.uuid4(),reverses=spent["expense"])
                compensate_movement(owner=owner,movement_id=Consumption.objects.get().movement_id,item_id=item.pk,quantity=Decimal("10"),key=uuid.uuid4(),reason="Sobra física")
                package = export_archive(owner)
            # This is Django's disposable test database, never the development database.
            call_command("flush", verbosity=0, interactive=False)
            owner = get_user_model().objects.create_user(
                username="destination", email="destination@example.test"
            )
            with override_settings(MEDIA_ROOT=destination):
                count = import_archive(owner=owner, package=package)
                self.assertEqual(count, len(package["payload"]["records"]))
                restored = Material.objects.get(pk=material.pk)
                self.assertEqual(restored.owner, owner)
                self.assertEqual(restored.physical_stock, Decimal("468"))
                self.assertEqual(restored.reserved_stock, Decimal("70"))
                self.assertEqual(Consumption.objects.count(), 1)
                from production.models import ActualExpense
                from production.costs import cost_summary
                self.assertEqual(ActualExpense.objects.count(),2)
                self.assertEqual(cost_summary(Order.objects.get())["expenses"],Decimal("0"))
                self.assertEqual(cost_summary(Order.objects.get())["materials"],Decimal("4"))
                self.assertEqual(Payment.objects.count(), 1)
                self.assertEqual(Order.objects.get().net_received, Decimal("20"))
                imported = QuoteVersion.objects.get(pk=version.pk)
                self.assertEqual(bytes(imported.pdf), original_pdf)
                self.assertEqual(imported.approval_origin, "imported")
                self.assertFalse(
                    ShareToken.objects.filter(revoked_at__isnull=True).exists()
                )
                asset = FileAsset.objects.get()
                self.assertTrue((Path(destination) / asset.file.name).exists())
                self.assertEqual(
                    create_order(owner=owner, version_id=version.pk).pk, order.pk
                )
                with self.assertRaises(ValidationError):
                    create_order(owner=owner, version_id=version2.pk)
                with self.assertRaises(ValidationError):
                    apply_amendment(
                        owner=owner, order_id=order.pk, version_id=amendment.pk
                    )
                call_command("reconcile_stock", verbosity=0)


class TableLimitTests(TestCase):
    def test_table_limits_reject_large_dimensions_before_iteration(self):
        workbook = Workbook()
        workbook.active["AO2"] = "Muito larga"
        output = BytesIO()
        workbook.save(output)
        with self.assertRaises(ValidationError):
            read_table(SimpleUploadedFile("large.xlsx", output.getvalue()))
        raw = ("nome;tipo;unidade\n" + "Fio;fio;g\n" * 2001).encode()
        with self.assertRaises(ValidationError):
            read_table(SimpleUploadedFile("large.csv", raw))

    def test_corrupted_xlsx_xml_becomes_a_validation_error(self):
        import zipfile

        workbook = Workbook()
        workbook.active["A1"] = "nome"
        output = BytesIO()
        workbook.save(output)
        broken = BytesIO()
        with zipfile.ZipFile(BytesIO(output.getvalue())) as source, zipfile.ZipFile(
            broken, "w"
        ) as destination:
            for info in source.infolist():
                destination.writestr(
                    info,
                    (
                        b"<worksheet><broken>"
                        if info.filename == "xl/worksheets/sheet1.xml"
                        else source.read(info.filename)
                    ),
                )
        with self.assertRaises(ValidationError):
            read_table(SimpleUploadedFile("broken.xlsx", broken.getvalue()))


class ArchiveBoundsTests(TestCase):
    def test_export_refuses_to_truncate_history_beyond_record_limit(self):
        from unittest.mock import patch
        from .archive import export_archive
        owner=get_user_model().objects.create_user(username='export_limit',email='export_limit@example.test')
        Material.objects.create(owner=owner,name='Primeiro',kind='yarn',unit='g')
        Material.objects.create(owner=owner,name='Segundo',kind='yarn',unit='g')
        with patch('portability.archive.MAX_RECORDS',1), self.assertRaises(ValidationError):
            export_archive(owner)
        self.assertEqual(Material.objects.filter(owner=owner).count(),2)

    def test_export_checks_encoded_package_budget(self):
        from unittest.mock import patch
        from .archive import export_archive
        owner=get_user_model().objects.create_user(username='export_bytes',email='export_bytes@example.test')
        Material.objects.create(owner=owner,name='Fio',kind='yarn',unit='g',notes='x'*2000)
        with patch('portability.archive.MAX_ARCHIVE_BYTES',2500), self.assertRaises(ValidationError):
            export_archive(owner)


class MetadataTemplateTests(TestCase):
    def test_template_metadata_mapping_is_preserved_at_confirmation(self):
        owner=get_user_model().objects.create_user(username='template_metadata',email='template_metadata@example.test')
        self.client.force_login(owner)
        response=self.client.get(reverse('portability:template',args=['xlsx']))
        self.assertIn('spreadsheetml',response['Content-Type'])
        workbook=Workbook()
        workbook.active.append(['nome','tipo','unidade','tecido','limite'])
        workbook.active.append(['Novo fio','fio','g','Algodão',12.5])
        output=BytesIO();workbook.save(output)
        mapping={name:name for name in COLUMNS}
        mapping.update(composicao='tecido',estoque_minimo='limite')
        job=preview_import(owner=owner,upload=SimpleUploadedFile('materiais.xlsx',output.getvalue()),mapping=mapping,locale='pt-br',separator=';',sheet='')
        confirm_import(owner=owner,job_id=job.pk)
        material=Material.objects.get(owner=owner)
        self.assertEqual(material.composition,'Algodão')
        self.assertEqual(material.minimum_stock,Decimal('12.5'))
        self.assertEqual(material.physical_stock,0)


class PreviewQuotaTests(TestCase):
    def test_quota_and_discard_preserve_stock_and_block_foreign_ids(self):
        owner=get_user_model().objects.create_user(username='preview_quota',email='preview_quota@example.test')
        other=get_user_model().objects.create_user(username='preview_quota_other',email='preview_quota_other@example.test')
        from .models import ImportJob
        job=ImportJob.objects.create(owner=owner,rows=[])
        mapping={name:name for name in COLUMNS}
        with override_settings(MAX_IMPORT_PREVIEWS=1),self.assertRaises(ValidationError):
            preview_import(owner=owner,upload=SimpleUploadedFile('table.csv',b'nome;tipo;unidade\nFio;fio;g'),mapping=mapping,locale='pt-br')
        self.client.force_login(other)
        url=reverse('portability:discard',args=[job.pk])
        self.assertEqual(self.client.post(url,{}).status_code,404)
        self.client.force_login(owner)
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url,{}).status_code,302)
        self.assertFalse(ImportJob.objects.filter(pk=job.pk).exists())
        self.assertFalse(Material.objects.filter(owner=owner).exists())
