"""Music business rules called by the views."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Q

from .models import Album, Review, Track


def search_tracks(owner, query=""):
    qs = Track.objects.filter(owner=owner).select_related("album")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return qs


def get_discover_tracks(user, query=""):
    """Return other users' tracks for the public discovery section."""
    qs = Track.objects.exclude(owner=user).select_related("owner", "album")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return qs.order_by("-uploaded_at", "-pk")


def get_neighbors(track):
    """Return the previous and next track in the album or ungrouped library."""
    if track.album_id:
        qs = Track.objects.filter(album_id=track.album_id)
    else:
        qs = Track.objects.filter(owner_id=track.owner_id, album__isnull=True)
    prev_track = qs.filter(id__lt=track.id).order_by("-id").first()
    next_track = qs.filter(id__gt=track.id).order_by("id").first()
    return prev_track, next_track


def average_rating(obj):
    """Return the average track or album rating, or None when unrated."""
    value = obj.reviews.aggregate(avg=Avg("rating"))["avg"]
    return round(value, 1) if value is not None else None


def ensure_owner(user, obj):
    if obj.owner_id != user.id:
        raise PermissionDenied("Only the owner can perform this action.")


def delete_track(user, track):
    ensure_owner(user, track)
    track.audio_file.delete(save=False)
    track.delete()


def create_track(user, *, title, artist, album, audio_file):
    if album is not None:
        ensure_owner(user, album)
    track = Track(
        owner=user,
        title=title,
        artist=artist,
        album=album,
        audio_file=audio_file,
    )
    track.full_clean()
    track.save()
    return track


def create_album(user, *, title, cover=None):
    album = Album(owner=user, title=title, cover=cover)
    album.full_clean()
    album.save()
    return album


def update_track(user, track, *, title, artist, album, audio_file=None):
    """Update a track after checking ownership and access to its album."""
    ensure_owner(user, track)
    if album is not None:
        ensure_owner(user, album)

    track.title = title
    track.artist = artist
    track.album = album
    previous_audio = track.audio_file
    if audio_file is not None:
        track.audio_file = audio_file
    track.full_clean()
    track.save()
    if (
        audio_file is not None
        and previous_audio
        and previous_audio.name != track.audio_file.name
    ):
        previous_audio.delete(save=False)
    return track


def update_album(user, album, *, title, cover=None):
    ensure_owner(user, album)
    previous_cover = album.cover
    album.title = title
    if cover is not None:
        album.cover = cover
    album.full_clean()
    album.save()
    if (
        cover is not None
        and previous_cover
        and previous_cover.name != album.cover.name
    ):
        previous_cover.delete(save=False)
    return album


def delete_album(user, album):
    ensure_owner(user, album)
    cover = album.cover
    album.delete()  # Track.album uses SET_NULL; tracks remain in the library.
    if cover:
        cover.delete(save=False)


def add_review(author, rating, text, *, track=None, album=None):
    if (track is None) == (album is None):
        raise ValueError("A review must target exactly one track or album.")
    target = {"track": track} if track is not None else {"album": album}
    if Review.objects.filter(author=author, **target).exists():
        raise ValidationError("You have already reviewed this item.")
    review = Review(author=author, rating=rating, text=text, **target)
    review.full_clean(validate_constraints=False)
    review.save()
    return review
