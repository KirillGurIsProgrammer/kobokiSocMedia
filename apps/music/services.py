"""Music business rules called by the views."""
import os
import random
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Exists, Max, OuterRef, Q
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import Follow
from .models import (
    Album,
    CollaborativePlaylist,
    CollaborativePlaylistInvite,
    CollaborativePlaylistMember,
    CollaborativePlaylistTrack,
    Like,
    ListenAlong,
    MusicSettings,
    NowPlaying,
    Playlist,
    PlaylistTrack,
    Review,
    SavedPlaylist,
    Tag,
    Track,
    TrackTag,
)


_TRACK_NOISE = re.compile(
    r"\s*[\(\[\{][^\)\]\}]*(?:official\s+video|(?:\d+\s*)?kbps)[^\)\]\}]*[\)\]\}]",
    re.IGNORECASE,
)
_TRACK_URL = re.compile(
    r"(?:https?://|www\.)\S+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?",
    re.IGNORECASE,
)
_TRACK_NUMBER = re.compile(r"^\s*\d+\s*(?:[.\-–—]\s*|\s+)")
_TRACK_SEPARATOR = re.compile(r"\s[-–—]\s")


def parse_track_filename(filename):
    """Return artist and title parsed from a track file's name."""
    stem = os.path.splitext(str(filename or "").replace("\\", "/"))[0]
    if not _TRACK_URL.search(stem):
        stem = stem.rsplit("/", 1)[-1]
    stem = stem.replace("_", " ")
    stem = _TRACK_NOISE.sub(" ", stem)
    stem = _TRACK_URL.sub(" ", stem)
    stem = _TRACK_NUMBER.sub("", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    separator = _TRACK_SEPARATOR.search(stem)
    if separator is None:
        return "", stem

    artist = stem[:separator.start()].strip()
    title = stem[separator.end():].strip()
    return artist, title


def normalize_tag_names(values):
    """Normalize comma-separated tag names and enforce per-track limits."""
    raw_names = values.split(",") if isinstance(values, str) else values or []
    names = []
    for raw_name in raw_names:
        name = str(raw_name).replace("#", "").strip().casefold()
        if not name:
            continue
        if not 2 <= len(name) <= 30:
            raise ValidationError("Тег должен содержать от 2 до 30 символов.")
        if name not in names:
            names.append(name)
    if len(names) > 10:
        raise ValidationError("К одному треку можно добавить не больше 10 тегов.")
    return names


def _get_or_create_tag(name):
    existing = Tag.objects.filter(name=name).first()
    if existing:
        return existing

    base_slug = slugify(name, allow_unicode=True) or "tag"
    slug = base_slug
    suffix = 2
    while Tag.objects.filter(slug=slug).exclude(name=name).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    tag, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
    return tag


def set_track_tags(user, track, names):
    ensure_owner(user, track)
    normalized = normalize_tag_names(names)
    tags = [_get_or_create_tag(name) for name in normalized]
    TrackTag.objects.filter(track=track).exclude(tag__in=tags).delete()
    existing_ids = set(TrackTag.objects.filter(track=track).values_list("tag_id", flat=True))
    TrackTag.objects.bulk_create(
        [TrackTag(track=track, tag=tag) for tag in tags if tag.pk not in existing_ids]
    )
    return tags


def with_like_data(queryset, user):
    likes_by_user = Like.objects.filter(track_id=OuterRef("pk"), user=user)
    return queryset.annotate(
        like_count=Count("likes", distinct=True),
        liked_by_user=Exists(likes_by_user),
    ).prefetch_related("track_tags__tag")


def search_tracks(owner, query="", *, user=None):
    qs = Track.objects.filter(owner=owner).select_related("album", "owner")
    if user is not None:
        qs = with_like_data(qs, user)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return qs


def get_discover_tracks(user, query=""):
    tracks = get_recommendations(user, limit=None)
    if query:
        query = query.casefold()
        tracks = [track for track in tracks if query in track.title.casefold() or query in track.artist.casefold()]
    return tracks


def get_recommendations(user, limit=20):
    """Rank community tracks; an unlimited result includes the full catalog."""
    if limit is not None and limit <= 0:
        return []
    liked = list(
        Like.objects.filter(user=user)
        .select_related("track")
        .prefetch_related("track__track_tags__tag")
    )
    if liked:
        taste_tracks = [like.track for like in liked]
        excluded_ids = {like.track_id for like in liked} if limit is not None else set()
    else:
        taste_ids = set(
            NowPlaying.objects.filter(user=user).values_list("track_id", flat=True)
        )
        taste_ids.update(
            PlaylistTrack.objects.filter(
                Q(playlist__owner=user) | Q(playlist__saves__user=user)
            ).values_list("track_id", flat=True)
        )
        taste_tracks = list(
            Track.objects.filter(pk__in=taste_ids).prefetch_related("track_tags__tag")
        )
        excluded_ids = set()

    artists = {track.artist for track in taste_tracks if track.artist}
    tag_names = {}
    tag_ids = set()
    for track in taste_tracks:
        for relation in track.track_tags.all():
            tag_ids.add(relation.tag_id)
            tag_names[relation.tag_id] = relation.tag.name

    candidates = Track.objects.exclude(owner=user).exclude(pk__in=excluded_ids)
    if limit is not None and (artists or tag_ids):
        candidate_filter = Q()
        if artists:
            candidate_filter |= Q(artist__in=artists)
        if tag_ids:
            candidate_filter |= Q(track_tags__tag_id__in=tag_ids)
        candidates = candidates.filter(candidate_filter).distinct()

    candidates = list(
        with_like_data(candidates.select_related("owner", "album"), user)
    )
    ranked = []
    for track in candidates:
        matched_ids = tag_ids.intersection(
            relation.tag_id for relation in track.track_tags.all()
        )
        track.recommendation_tag_count = len(matched_ids)
        if matched_ids:
            matched_name = tag_names[min(matched_ids)]
            track.recommendation_reason = f"Совпадает: {matched_name}"
        elif track.artist in artists:
            track.recommendation_reason = f"Тот же исполнитель: {track.artist}"
        else:
            track.recommendation_reason = "Новая загрузка"
        ranked.append(track)

    random.shuffle(ranked)
    ranked.sort(
        key=lambda track: (
            -track.recommendation_tag_count,
            track.like_count,
        )
    )

    if limit is None:
        return ranked

    result = []
    author_counts = {}
    last_author_id = None
    author_streak = 0
    while ranked and len(result) < limit:
        for index, track in enumerate(ranked):
            count = author_counts.get(track.owner_id, 0)
            streak = author_streak + 1 if track.owner_id == last_author_id else 1
            if count >= 3 or streak > 2:
                continue
            result.append(track)
            author_counts[track.owner_id] = count + 1
            author_streak = streak
            last_author_id = track.owner_id
            ranked.pop(index)
            break
        else:
            break
    return result


def get_radio_tracks(user, tag, *, limit=10, exclude_ids=()):
    if limit <= 0:
        return []
    queryset = Track.objects.filter(tags=tag).exclude(pk__in=exclude_ids)
    queryset = with_like_data(queryset.select_related("owner", "album"), user)
    return list(queryset.order_by("?")[:limit])


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


def save_now_playing(user, *, track_id, playlist_id=None, position_seconds=0,
                     duration_seconds=0, is_playing=False):
    try:
        track = Track.objects.get(pk=track_id)
    except (Track.DoesNotExist, TypeError, ValueError):
        raise ValidationError("Трек не найден.")
    try:
        position_seconds = max(0, float(position_seconds))
        duration_seconds = max(0, float(duration_seconds))
    except (TypeError, ValueError):
        raise ValidationError("Позиция или длительность трека указана неверно.")
    if duration_seconds:
        position_seconds = min(position_seconds, duration_seconds)
    if not isinstance(is_playing, bool):
        raise ValidationError("Состояние воспроизведения указано неверно.")

    playlist = None
    if playlist_id not in (None, ""):
        playlist = get_viewable_playlist(user, playlist_id)
        if playlist is None or not PlaylistTrack.objects.filter(playlist=playlist, track=track).exists():
            raise ValidationError("Плейлист недоступен для этого трека.")

    return NowPlaying.objects.update_or_create(
        user=user,
        defaults={
            "track": track,
            "playlist": playlist,
            "position_seconds": position_seconds,
            "duration_seconds": duration_seconds,
            "is_playing": is_playing,
        },
    )[0]


def now_playing_snapshot(subject, viewer):
    settings = MusicSettings.objects.filter(user=subject).first()
    if settings is not None and not settings.show_now_playing and subject.pk != viewer.pk:
        return {"visible": False}

    state = NowPlaying.objects.filter(user=subject).select_related(
        "track__owner", "track__album", "playlist"
    ).first()
    if state is None:
        return {
            "visible": True,
            "is_listening": False,
            "last_seen_minutes": None,
            "listener_count": active_listener_count(subject),
        }

    now = timezone.now()
    age_seconds = max(0, (now - state.updated_at).total_seconds())
    fresh = age_seconds <= 15
    if not fresh:
        return {
            "visible": True,
            "is_listening": False,
            "last_seen_minutes": max(1, int((age_seconds + 59) // 60)),
            "listener_count": 0,
        }

    position = state.position_seconds
    if state.is_playing:
        position += age_seconds
    if state.duration_seconds:
        position = min(position, state.duration_seconds)
    visible_playlist = state.playlist
    if (
        visible_playlist is not None
        and not visible_playlist.is_public
        and (viewer is None or visible_playlist.owner_id != viewer.pk)
    ):
        visible_playlist = None
    return {
        "visible": True,
        "is_listening": state.is_playing,
        "is_playing": state.is_playing,
        "track": state.track,
        "playlist": visible_playlist,
        "position_seconds": position,
        "duration_seconds": state.duration_seconds,
        "updated_at": state.updated_at,
        "last_seen_minutes": None,
        "listener_count": active_listener_count(subject),
    }


def can_join_session(listener, host):
    if listener.pk == host.pk:
        return False
    preferences = MusicSettings.objects.filter(user=host).first()
    if preferences is not None:
        if not preferences.show_now_playing or preferences.allow_join == MusicSettings.JOIN_NOBODY:
            return False
        if preferences.allow_join == MusicSettings.JOIN_FOLLOWERS and not Follow.objects.filter(
            follower=listener, following=host
        ).exists():
            return False
    return NowPlaying.objects.filter(
        user=host,
        updated_at__gte=timezone.now() - timedelta(seconds=15),
    ).exists()


def join_session(listener, host):
    if listener.pk == host.pk:
        raise ValidationError("Нельзя подключиться к собственному плееру.")
    if not can_join_session(listener, host):
        raise PermissionDenied("Сеанс недоступен или пользователь не делится музыкой.")
    session, _created = ListenAlong.objects.update_or_create(
        listener=listener,
        defaults={"host": host},
    )
    return session


def leave_session(listener):
    ListenAlong.objects.filter(listener=listener).delete()


def active_listener_count(host):
    cutoff = timezone.now() - timedelta(seconds=15)
    return ListenAlong.objects.filter(
        host=host,
        listener__music_now_playing__updated_at__gte=cutoff,
    ).count()


def get_listen_along(listener):
    return ListenAlong.objects.filter(listener=listener).select_related("host").first()


def update_music_settings(user, *, show_now_playing, allow_join):
    valid_values = {choice for choice, _label in MusicSettings.JOIN_CHOICES}
    if allow_join not in valid_values:
        raise ValidationError("Неизвестный режим совместного прослушивания.")
    settings, _created = MusicSettings.objects.update_or_create(
        user=user,
        defaults={"show_now_playing": show_now_playing, "allow_join": allow_join},
    )
    return settings


def create_collaborative_playlist(user, *, title, invitees):
    invitees = list(dict.fromkeys(invitees))
    if not title.strip():
        raise ValidationError("Укажите название плейлиста.")
    if not invitees:
        raise ValidationError("Выберите хотя бы одного пользователя для приглашения.")
    if user in invitees or Follow.objects.filter(follower=user, following__in=invitees).count() != len(invitees):
        raise PermissionDenied("Приглашать можно только пользователей, на которых вы подписаны.")
    with transaction.atomic():
        playlist = CollaborativePlaylist.objects.create(creator=user, title=title.strip())
        CollaborativePlaylistMember.objects.create(playlist=playlist, user=user)
        CollaborativePlaylistInvite.objects.bulk_create([
            CollaborativePlaylistInvite(playlist=playlist, user=invitee) for invitee in invitees
        ])
    return playlist


def respond_collaborative_invite(user, invite, *, accept):
    if invite.user_id != user.pk or invite.status != CollaborativePlaylistInvite.PENDING:
        raise PermissionDenied("Это приглашение недоступно.")
    with transaction.atomic():
        invite.status = CollaborativePlaylistInvite.ACCEPTED if accept else CollaborativePlaylistInvite.DECLINED
        invite.save(update_fields=["status"])
        if accept:
            CollaborativePlaylistMember.objects.get_or_create(playlist=invite.playlist, user=user)
    return invite


def ensure_collaborative_member(user, playlist):
    if playlist.creator_id != user.pk and not playlist.memberships.filter(user=user).exists():
        raise PermissionDenied("Плейлист доступен только участникам.")


def leave_collaborative_playlist(user, playlist):
    ensure_collaborative_member(user, playlist)
    if playlist.creator_id == user.pk:
        raise ValidationError("Создатель не может выйти из своего плейлиста.")
    playlist.memberships.filter(user=user).delete()
    CollaborativePlaylistInvite.objects.filter(playlist=playlist, user=user).delete()


def delete_collaborative_playlist(user, playlist):
    if playlist.creator_id != user.pk:
        raise PermissionDenied("Удалить плейлист может только создатель.")
    playlist.delete()


def add_collaborative_playlist_track(user, playlist, track):
    ensure_collaborative_member(user, playlist)
    with transaction.atomic():
        position = playlist.track_entries.aggregate(value=Max("position"))["value"]
        _entry, created = CollaborativePlaylistTrack.objects.get_or_create(
            playlist=playlist,
            track=track,
            defaults={
                "added_by": user,
                "position": 0 if position is None else position + 1,
            },
        )
    return created


def remove_collaborative_playlist_track(user, playlist, track):
    ensure_collaborative_member(user, playlist)
    deleted, _details = CollaborativePlaylistTrack.objects.filter(
        playlist=playlist,
        track=track,
    ).delete()
    return bool(deleted)


def get_collaborative_playlist_tracks(user, playlist):
    ensure_collaborative_member(user, playlist)
    entries = (
        CollaborativePlaylistTrack.objects.filter(playlist=playlist)
        .select_related("track", "track__owner", "track__album", "added_by")
        .prefetch_related("track__track_tags__tag")
        .order_by("position", "pk")
    )
    tracks = []
    for entry in entries:
        entry.track.brought_by = entry.added_by
        entry.track.collaborative_entry = entry
        tracks.append(entry.track)
    return tracks


def get_music_settings(user):
    settings = MusicSettings.objects.filter(user=user).first()
    if settings is not None:
        return settings
    return MusicSettings(user=user)


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


def create_track(user, *, title, artist, album, audio_file, cover=None, tags=None):
    if album is not None:
        ensure_owner(user, album)
    normalized_tags = normalize_tag_names(tags) if tags is not None else None
    track = Track(
        owner=user,
        title=title,
        artist=artist,
        album=album,
        audio_file=audio_file,
        cover=cover,
    )
    track.full_clean()
    track.save()
    if normalized_tags is not None:
        set_track_tags(user, track, normalized_tags)
    return track


def create_album(user, *, title, cover=None):
    album = Album(owner=user, title=title, cover=cover)
    album.full_clean()
    album.save()
    return album


def update_track(user, track, *, title, artist, album, audio_file=None, cover=None, tags=None):
    """Update a track after checking ownership and access to its album."""
    ensure_owner(user, track)
    if album is not None:
        ensure_owner(user, album)
    normalized_tags = normalize_tag_names(tags) if tags is not None else None

    track.title = title
    track.artist = artist
    track.album = album
    previous_audio = track.audio_file
    previous_cover = track.cover
    if audio_file is not None:
        track.audio_file = audio_file
    if cover is not None:
        track.cover = cover
    track.full_clean()
    track.save()
    if (
        audio_file is not None
        and previous_audio
        and previous_audio.name != track.audio_file.name
    ):
        previous_audio.delete(save=False)
    if (
        cover is not None
        and previous_cover
        and previous_cover.name != track.cover.name
    ):
        previous_cover.delete(save=False)
    if normalized_tags is not None:
        set_track_tags(user, track, normalized_tags)
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
