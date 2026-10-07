import tempfile
from io import BytesIO
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from projects.services import create_project
from .services import create_quote, add_quote_item, publish, reissue_token
from .files import attach_image


class FileTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.owner = get_user_model().objects.create_user(
            username="photos", email="photos@example.test"
        )
        project = create_project(
            owner=self.owner,
            name="Peça",
            estimated_seconds=3600,
            hourly_rate=Decimal("10"),
        )
        quote = create_quote(owner=self.owner)
        self.version = quote.versions.get()
        add_quote_item(
            owner=self.owner,
            version_id=self.version.pk,
            project_id=project.pk,
            quantity=1,
        )

    def upload(self):
        output = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(output, format="PNG")
        return SimpleUploadedFile(
            "foto.png", output.getvalue(), content_type="image/png"
        )

    def test_public_image_is_authorized_and_private_image_is_not_in_projection(self):
        private = attach_image(
            owner=self.owner,
            version_id=self.version.pk,
            upload=self.upload(),
            label="REFERÊNCIA INTERNA",
            is_public=False,
        )
        public = attach_image(
            owner=self.owner,
            version_id=self.version.pk,
            upload=self.upload(),
            label="Imagem da peça",
            is_public=True,
        )
        version, raw = publish(owner=self.owner, version_id=self.version.pk)
        self.assertEqual(
            [entry["id"] for entry in version.public_snapshot["images"]],
            [str(public.asset_id)],
        )
        self.assertEqual(
            self.client.get(
                reverse("sales:portal_image", args=[raw, private.asset_id])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("sales:portal_image", args=[raw, public.asset_id])
            ).status_code,
            200,
        )
        reissue_token(owner=self.owner, version_id=version.pk)
        self.assertEqual(
            self.client.get(
                reverse("sales:portal_image", args=[raw, public.asset_id])
            ).status_code,
            404,
        )

    def test_private_download_requires_owner(self):
        image = attach_image(
            owner=self.owner,
            version_id=self.version.pk,
            upload=self.upload(),
            label="Privada",
        )
        other = get_user_model().objects.create_user(
            username="other", email="other@example.test"
        )
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(
                reverse("sales:owner_image", args=[image.asset_id])
            ).status_code,
            404,
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(
                reverse("sales:owner_image", args=[image.asset_id])
            ).status_code,
            200,
        )

    def test_svg_disguised_as_png_is_rejected(self):
        bad = SimpleUploadedFile(
            "photo.png",
            b"<svg><script>alert(1)</script></svg>",
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            attach_image(
                owner=self.owner,
                version_id=self.version.pk,
                upload=bad,
                label="Malicioso",
            )

    def test_published_version_does_not_accept_new_images(self):
        version, _ = publish(owner=self.owner, version_id=self.version.pk)
        with self.assertRaises(ValidationError):
            attach_image(
                owner=self.owner,
                version_id=version.pk,
                upload=self.upload(),
                label="Nova",
            )

    def test_explicit_revocation_disables_portal_pdf_and_images_without_erasing_version(
        self,
    ):
        from .services import revoke_links

        image = attach_image(
            owner=self.owner,
            version_id=self.version.pk,
            upload=self.upload(),
            label="Peça",
            is_public=True,
        )
        version, raw = publish(owner=self.owner, version_id=self.version.pk)
        pdf = bytes(version.pdf)
        self.assertEqual(revoke_links(owner=self.owner, version_id=version.pk), 1)
        self.assertEqual(revoke_links(owner=self.owner, version_id=version.pk), 0)
        for name, args in [
            ("portal", [raw]),
            ("portal_pdf", [raw]),
            ("portal_image", [raw, image.asset_id]),
        ]:
            self.assertEqual(
                self.client.get(reverse("sales:" + name, args=args)).status_code, 404
            )
        version.refresh_from_db()
        self.assertEqual(bytes(version.pdf), pdf)
