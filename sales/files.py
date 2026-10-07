import hashlib
import uuid
import warnings
from io import BytesIO
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from PIL import Image, UnidentifiedImageError
from .models import FileAsset, QuoteImage, QuoteVersion


def normalized_image(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError("A imagem excede 5 MB.")
    data = upload.read(5 * 1024 * 1024 + 1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            if (
                image.format not in {"JPEG", "PNG", "WEBP"}
                or image.width * image.height > 16_000_000
            ):
                raise ValidationError(
                    "Use JPEG, PNG ou WebP de até 16 milhões de pixels."
                )
            image.verify()
            image = Image.open(BytesIO(data))
            image.load()
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.thumbnail((1600, 1600))
            image.info.clear()
            output = BytesIO()
            extension = "png" if image.mode == "RGBA" else "jpg"
            image.save(
                output,
                format="PNG" if extension == "png" else "JPEG",
                optimize=True,
                **({"quality": 85} if extension == "jpg" else {}),
            )
            if output.tell() > 5 * 1024 * 1024:
                raise ValidationError(
                    "Imagem compactada ainda excede o limite. Reduza suas dimensões."
                )
            return output.getvalue(), extension, image.width, image.height
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError(
            "Imagem inválida, corrompida ou excessivamente grande."
        ) from exc


@transaction.atomic
def attach_image(*, owner, version_id, upload, label, is_public=False):
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    version = get_object_or_404(
        QuoteVersion.objects.select_for_update(), pk=version_id, quote__owner=owner
    )
    if version.published_at:
        raise ValidationError("Imagens publicadas são imutáveis. Crie outra versão.")
    if (
        FileAsset.objects.filter(owner=owner).count()
        >= settings.MAX_PRIVATE_IMAGES_PER_USER
    ):
        raise ValidationError(
            "Limite de imagens da conta atingido. Preserve o histórico e revise imagens sem uso."
        )
    if version.images.count() >= settings.MAX_IMAGES_PER_QUOTE:
        raise ValidationError("Limite de imagens desta versão atingido.")
    data, extension, width, height = normalized_image(upload)
    asset = FileAsset(
        owner=owner,
        label=label,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        width=width,
        height=height,
    )
    filename = f"{owner.pk}/{uuid.uuid4()}.{extension}"
    asset.file.save(filename, ContentFile(data), save=False)
    try:
        asset.save()
        link = QuoteImage.objects.create(
            version=version, asset=asset, is_public=is_public
        )
    except Exception:
        asset.file.storage.delete(asset.file.name)
        raise
    return link
