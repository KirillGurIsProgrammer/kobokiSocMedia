"""Music business rules called by the views."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Exists, OuterRef, Q

from .models import Album, Like, Playlist, PlaylistTrack, Review, SavedPlaylist, Track


def with_like_data(queryset, user):
    likes_by_user = Like.objects.filter(track_id=OuterRef("pk"), user=user)
    return queryset.annotate(
        like_count=Count("likes", distinct=True),
        liked_by_user=Exists(likes_by_user),
    )


def search_tracks(owner, query="", *, user=None):
    qs = Track.objects.filter(owner=owner).select_related("album", "owner")
    if user is not None:
        qs = with_like_data(qs, user)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return qs


def get_discover_tracks(user, query=""):
    """Return other users' tracks for the public discovery section."""
    qs = with_like_data(
        Track.objects.exclude(owner=user).select_related("owner", "album"), user
    )
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return qs.order_by("-uploaded_at", "-pk")


def toggle_like(user, track):
    """Toggle a user's like and return (liked, current_like_count)."""
    try:
        with transaction.atomic():
            like, created = Like.objects.get_or_create(user=user, track=track)
            if not created:
                like.delete()
                liked = False
            else:
                liked = True
    except IntegrityError:
        # A concurrent request may have created the unique pair first.
        liked = Like.objects.filter(user=user, track=track).exists()
    return liked, Like.objects.filter(track=track).count()


def get_viewable_playlist(user, playlist_id):
    """Return a public playlist or the user's own playlist, otherwise None."""
    return (
        Playlist.objects.filter(pk=playlist_id)
        .filter(Q(owner=user) | Q(is_public=True))
        .select_related("owner")
        .first()
    )


def get_owned_playlist(user, playlist_id):
    return Playlist.objects.filter(pk=playlist_id, owner=user).first()


def list_user_playlists(user):
    return Playlist.objects.filter(owner=user).annotate(track_count=Count("playlist_tracks"))


def list_saved_playlists(user):
    saved_by_user = SavedPlaylist.objects.filter(
        user=user, playlist_id=OuterRef("pk")
    )
    return (
        Playlist.objects.filter(saves__user=user, is_public=True)
        .select_related("owner")
        .annotate(
            track_count=Count("playlist_tracks"),
            saved_by_user=Exists(saved_by_user),
        )
    )


def list_public_playlists(user):
    saved_by_user = SavedPlaylist.objects.filter(
        user=user, playlist_id=OuterRef("pk")
    )


def list_liked_tracks(user):
    return with_like_data(
        Track.objects.filter(likes__user=user).select_related("owner", "album"), user
    ).order_by("-likes__created_at", "-pk")
    return (
        Playlist.objects.filter(is_public=True)
        .exclude(owner=user)
        .select_related("owner")
        .annotate(
            track_count=Count("playlist_tracks"),
            saved_by_user=Exists(saved_by_user),
        )
    )


def get_playlist_entries(user, playlist):
    entries = list(
        PlaylistTrack.objects.filter(playlist=playlist).select_related("track__owner", "track__album")
    )
    tracks = with_like_data(
        Track.objects.filter(pk__in=[entry.track_id for entry in entries]).select_related("owner", "album"),
        user,
    )
    tracks_by_id = {track.pk: track for track in tracks}
    for entry in entries:
        entry.track = tracks_by_id[entry.track_id]
    return entries


def create_playlist(user, *, title, description="", cover=None, is_public=True):
    playlist = Playlist(
        owner=user,
        title=title,
        description=description,
        cover=cover,
        is_public=is_public,
    )
    playlist.full_clean()
    playlist.save()
    return playlist


def update_playlist(user, playlist, *, title, description, is_public, cover=None):
    ensure_owner(user, playlist)
    previous_cover = playlist.cover
    playlist.title = title
    playlist.description = description
    playlist.is_public = is_public
    if cover is not None:
        playlist.cover = cover
    playlist.full_clean()
    playlist.save()
    if cover is not None and previous_cover and previous_cover.name != playlist.cover.name:
        previous_cover.delete(save=False)
    return playlist


def delete_playlist(user, playlist):
    ensure_owner(user, playlist)
    cover = playlist.cover
    playlist.delete()
    if cover:
        cover.delete(save=False)


def add_track_to_playlist(user, playlist, track):
    ensure_owner(user, playlist)
    if PlaylistTrack.objects.filter(playlist=playlist, track=track).exists():
        raise ValidationError("Этот трек уже есть в плейлисте.")
    position = PlaylistTrack.objects.filter(playlist=playlist).count()
    return PlaylistTrack.objects.create(playlist=playlist, track=track, position=position)


def remove_track_from_playlist(user, playlist, track):
    ensure_owner(user, playlist)
    with transaction.atomic():
        entry = PlaylistTrack.objects.get(playlist=playlist, track=track)
        entry.delete()
        for position, remaining in enumerate(
            PlaylistTrack.objects.filter(playlist=playlist).order_by("position", "pk")
        ):
            if remaining.position != position:
                PlaylistTrack.objects.filter(pk=remaining.pk).update(position=position)


def move_playlist_track(user, playlist, track, direction):
    ensure_owner(user, playlist)
    if direction not in {"up", "down"}:
        raise ValidationError("Неизвестное направление перемещения.")
    with transaction.atomic():
        entries = list(
            PlaylistTrack.objects.filter(playlist=playlist).order_by("position", "pk")
        )
        index = next((i for i, entry in enumerate(entries) if entry.track_id == track.pk), None)
        if index is None:
            raise PlaylistTrack.DoesNotExist
        target_index = index - 1 if direction == "up" else index + 1
        if 0 <= target_index < len(entries):
            entries[index].position, entries[target_index].position = (
                entries[target_index].position,
                entries[index].position,
            )
            entries[index].save(update_fields=("position",))
            entries[target_index].save(update_fields=("position",))


def toggle_saved_playlist(user, playlist):
    if not playlist.is_public:
        raise PermissionDenied("Нельзя сохранить приватный плейлист.")
    if playlist.owner_id == user.pk:
        raise ValidationError("Свой плейлист нельзя сохранить в коллекцию.")
    saved, created = SavedPlaylist.objects.get_or_create(user=user, playlist=playlist)
    if not created:
        saved.delete()
        return False
    return True


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
