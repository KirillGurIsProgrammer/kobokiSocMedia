from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.validators import validate_audio, validate_image

User = settings.AUTH_USER_MODEL


class Album(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="albums")
    title = models.CharField("Название", max_length=100)
    cover = models.ImageField(
        "Обложка", upload_to="covers/", blank=True, validators=[validate_image]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("music:album_detail", args=[self.pk])


class Track(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tracks")
    album = models.ForeignKey(
        Album, null=True, blank=True, on_delete=models.SET_NULL, related_name="tracks"
    )
    title = models.CharField("Название", max_length=100)
    artist = models.CharField("Исполнитель", max_length=100)
    audio_file = models.FileField(
        "Аудиофайл", upload_to="tracks/", validators=[validate_audio]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.artist} — {self.title}"

    def get_absolute_url(self):
        return reverse("music:track_detail", args=[self.pk])


class Review(models.Model):
    """Отзыв на трек ИЛИ на альбом (ровно одно из двух)."""

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    track = models.ForeignKey(
        Track, null=True, blank=True, on_delete=models.CASCADE, related_name="reviews"
    )
    album = models.ForeignKey(
        Album, null=True, blank=True, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        "Оценка", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.TextField("Отзыв", max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Django 5.1+: параметр называется condition (раньше был check)
            models.CheckConstraint(
                condition=(
                    Q(track__isnull=False, album__isnull=True)
                    | Q(track__isnull=True, album__isnull=False)
                ),
                name="review_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["author", "track"],
                condition=Q(track__isnull=False),
                name="unique_review_per_track",
            ),
            models.UniqueConstraint(
                fields=["author", "album"],
                condition=Q(album__isnull=False),
                name="unique_review_per_album",
            ),
        ]

    def __str__(self):
        return f"{self.author} · {self.rating}/5"
