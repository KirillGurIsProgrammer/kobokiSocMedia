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
    )
    track_artist = models.CharField(
        "Исполнитель",
        max_length=200,
        blank=True,
    )
    track_url = models.URLField(
        "Ссылка на трек",
        max_length=500,
        blank=True,
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
        track_fields = (self.track_title, self.track_artist, self.track_url)
        if any(track_fields) and not all(track_fields):
            raise ValidationError(
                {
                    "track_title": (
                        "To attach a track, provide its title, artist, and link."
                    ),
                    "track_artist": (
                        "To attach a track, provide its title, artist, and link."
                    ),
                    "track_url": (
                        "To attach a track, provide its title, artist, and link."
                    ),
                }
            )

    def __str__(self):
        return f"{self.author}: {self.text[:50]}"
