from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models

from apps.accounts.validators import validate_profile_image


class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    text = models.TextField(
        validators=[
            MinLengthValidator(1),
            MaxLengthValidator(2000),
        ],
    )
    image = models.ImageField(
        upload_to="posts/",
        blank=True,
        validators=[validate_profile_image],
    )
    track_title = models.CharField(
        "Название трека",
        max_length=200,
        blank=True,
        editable=False,
    )
    track_artist = models.CharField(
        "Исполнитель",
        max_length=200,
        blank=True,
        editable=False,
    )
    track_url = models.URLField(
        "Старая ссылка на трек",
        max_length=500,
        blank=True,
        editable=False,
    )
    track = models.ForeignKey(
        "music.Track",
        verbose_name="Трек",
        related_name="posts",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.text and not self.text.strip():
            raise ValidationError({"text": "Post text cannot be empty."})

    def __str__(self):
        return f"{self.author}: {self.text[:50]}"