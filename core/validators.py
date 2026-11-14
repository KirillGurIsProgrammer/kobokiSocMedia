from pathlib import Path

from django.core.exceptions import ValidationError

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".mp3", ".wav", ".ogg"}


def validate_attachment(upload):
    if upload.size > MAX_ATTACHMENT_SIZE:
        raise ValidationError("Размер вложения не должен превышать 10 МБ.")
    if Path(upload.name).suffix.lower() not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError("Этот формат вложения не поддерживается.")
