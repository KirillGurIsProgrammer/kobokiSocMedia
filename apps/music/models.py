from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.validators import validate_audio, validate_image

User = settings.AUTH_USER_MODEL


class Tag(models.Model):
    name = models.CharField("Название", max_length=30)
    slug = models.SlugField("Слаг", max_length=80, unique=True, allow_unicode=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("music:tag_detail", args=[self.slug])


class Album(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="albums")
    title = models.CharField("Title", max_length=100)
    cover = models.ImageField(
        "Cover", upload_to="covers/", blank=True, validators=[validate_image]
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
    title = models.CharField("Title", max_length=100)
    artist = models.CharField("Artist", max_length=100, blank=True)
    audio_file = models.FileField(
        "Audio file", upload_to="tracks/", validators=[validate_audio]
    )
    cover = models.ImageField(
        "Обложка трека",
        upload_to="track_covers/",
        blank=True,
        validators=[validate_image],
    )
    tags = models.ManyToManyField(Tag, through="TrackTag", related_name="tracks", blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.artist} — {self.title}"

    def get_absolute_url(self):
        return reverse("music:track_detail", args=[self.pk])


class TrackTag(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="track_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="track_tags")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("track", "tag"), name="unique_tag_per_track"),
        ]

    def __str__(self):
        return f"{self.track}: {self.tag}"


class Like(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="music_likes",
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "track"),
                name="unique_music_like_per_user_track",
            ),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user} likes {self.track}"


class Playlist(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="music_playlists",
    )
    title = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True, max_length=1000)
    cover = models.ImageField(
        "Обложка",
        upload_to="playlists/",
        blank=True,
        validators=[validate_image],
    )
    is_public = models.BooleanField("Публичный плейлист", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("music:playlist_detail", args=[self.pk])


class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="playlist_tracks",
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="playlist_entries",
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("playlist", "track"),
                name="unique_track_per_playlist",
            ),
        ]

    def __str__(self):
        return f"{self.playlist}: {self.track}"


class SavedPlaylist(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_music_playlists",
    )
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="saves",
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-saved_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "playlist"),
                name="unique_saved_playlist_per_user",
            ),
        ]


class NowPlaying(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="music_now_playing",
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="now_playing_sessions",
    )
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.SET_NULL,
        related_name="now_playing_sessions",
        blank=True,
        null=True,
    )
    position_seconds = models.FloatField(default=0, validators=[MinValueValidator(0)])
    duration_seconds = models.FloatField(default=0, validators=[MinValueValidator(0)])
    is_playing = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class MusicSettings(models.Model):
    JOIN_EVERYONE = "everyone"
    JOIN_FOLLOWERS = "followers"
    JOIN_NOBODY = "nobody"
    JOIN_CHOICES = [
        (JOIN_EVERYONE, "Все пользователи"),
        (JOIN_FOLLOWERS, "Подписчики"),
        (JOIN_NOBODY, "Никто"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="music_settings",
    )
    show_now_playing = models.BooleanField(default=True)
    allow_join = models.CharField(
        max_length=12,
        choices=JOIN_CHOICES,
        default=JOIN_EVERYONE,
    )


class ListenAlong(models.Model):
    listener = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="music_listen_along",
    )
    host = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="music_listeners",
    )
    joined_at = models.DateTimeField(auto_now_add=True)


class CollaborativePlaylist(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_collaborative_playlists")
    title = models.CharField("Название", max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return self.title


class CollaborativePlaylistInvite(models.Model):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    STATUS_CHOICES = [(PENDING, "Ожидает ответа"), (ACCEPTED, "Принято"), (DECLINED, "Отклонено")]

    playlist = models.ForeignKey(CollaborativePlaylist, on_delete=models.CASCADE, related_name="invites")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="music_playlist_invites")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("playlist", "user"), name="unique_music_collab_invite")]


class CollaborativePlaylistMember(models.Model):
    playlist = models.ForeignKey(CollaborativePlaylist, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="music_collaborative_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("playlist", "user"), name="unique_music_collab_member")]


class CollaborativePlaylistTrack(models.Model):
    playlist = models.ForeignKey(
        CollaborativePlaylist,
        on_delete=models.CASCADE,
        related_name="track_entries",
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="collaborative_playlist_entries",
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collaborative_playlist_tracks_added",
    )
    position = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("position", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("playlist", "track"),
                name="unique_track_per_collaborative_playlist",
            ),
        ]


class Review(models.Model):
    """A review for exactly one track or album."""

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    track = models.ForeignKey(
        Track, null=True, blank=True, on_delete=models.CASCADE, related_name="reviews"
    )
    album = models.ForeignKey(
        Album, null=True, blank=True, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        "Rating", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.TextField("Review", max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Django 5.1+: the argument is named condition (previously check).
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
