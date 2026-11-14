from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.music.models import Track
from apps.music.services import create_track
from .models import Post


_UNSET = object()


@dataclass(frozen=True)
class FeedEntry:
    kind: str
    item: Post | Track
    created_at: datetime


def create_post(
    author,
    *,
    text,
    image=None,
    track=None,
    track_file=None,
    track_title="",
    track_artist="",
):
    if not author.is_authenticated:
        raise PermissionDenied("Authentication is required to create posts.")
    post = Post(
        author=author,
        text=text,
        image=image,
        track=track,
    )
    post.full_clean()
    with transaction.atomic():
        if track_file:
            post.track = create_track(
                author,
                title=track_title,
                artist=track_artist,
                album=None,
                audio_file=track_file,
            )
        post.save()
    return post


def update_post(
    user,
    post,
    *,
    text,
    image=_UNSET,
    track=_UNSET,
    track_file=None,
    track_title="",
    track_artist="",
):
    if not can_manage_post(user, post):
        raise PermissionDenied("Only the post author can edit it.")
    post.text = text
    if image is not _UNSET:
        post.image = image
    if track is not _UNSET:
        post.track = track
    post.full_clean()
    with transaction.atomic():
        if track_file:
            post.track = create_track(
                user,
                title=track_title,
                artist=track_artist,
                album=None,
                audio_file=track_file,
            )
        post.save()
    return post


def can_manage_post(user, post):
    return user.is_authenticated and user.pk == post.author_id


def delete_post(user, post):
    if not can_manage_post(user, post):
        raise PermissionDenied("Only the post author can delete it.")
    post.delete()


def get_feed_for(_user):
    posts = Post.objects.select_related("author", "track").order_by("-created_at")
    tracks = Track.objects.select_related("owner", "album").order_by("-uploaded_at")
    entries = [
        FeedEntry("post", post, post.created_at)
        for post in posts
    ]
    entries.extend(
        FeedEntry("track", track, track.uploaded_at)
        for track in tracks
    )
    return sorted(entries, key=lambda entry: entry.created_at, reverse=True)
