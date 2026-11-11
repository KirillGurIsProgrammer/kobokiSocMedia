"""Shared file validators used by music, accounts, and messaging.

Validators are top-level functions rather than closures so Django can serialize
them in migrations.
"""
import os

from django.core.exceptions import ValidationError

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXT = {".mp3", ".ogg", ".wav"}


def _check(file, allowed, max_mb):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(f"Allowed formats: {', '.join(sorted(allowed))}")
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"File exceeds {max_mb} MB.")


def validate_image(file):
    _check(file, IMAGE_EXT, 5)


def validate_audio(file):
    _check(file, AUDIO_EXT, 20)


def validate_attachment(file):
    _check(file, IMAGE_EXT | AUDIO_EXT, 10)
