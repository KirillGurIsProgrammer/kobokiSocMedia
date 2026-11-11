"""Общие валидаторы файлов. Используются music, accounts, messaging.

Валидаторы — обычные функции верхнего уровня (не фабрики с замыканием),
иначе Django не сможет сериализовать их в миграции.
"""
import os

from django.core.exceptions import ValidationError

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXT = {".mp3", ".ogg", ".wav"}


def _check(file, allowed, max_mb):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(f"Допустимые форматы: {', '.join(sorted(allowed))}")
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Файл больше {max_mb} МБ")


def validate_image(file):
    _check(file, IMAGE_EXT, 5)


def validate_audio(file):
    _check(file, AUDIO_EXT, 20)


def validate_attachment(file):
    _check(file, IMAGE_EXT | AUDIO_EXT, 10)
