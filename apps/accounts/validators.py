from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError


MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_profile_image(image_file):
    if image_file.size > MAX_PROFILE_IMAGE_SIZE:
        raise ValidationError(_("Image must be no larger than 5 MB."))

    extension = Path(image_file.name).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError(_("Use a JPG, PNG, or WebP image."))

    try:
        with Image.open(image_file) as image:
            image.verify()
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError(_("Use a JPG, PNG, or WebP image."))
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ValidationError(_("Upload a valid image file.")) from exc
    finally:
        image_file.seek(0)
