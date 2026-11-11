from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from .models import Post


_UNSET = object()


def create_post(
    author,
    *,
    text,
    image=None,
    track_title="",
    track_artist="",
    track_url="",
):
    if not author.is_authenticated:
        raise PermissionDenied("Authentication is required to create posts.")
    post = Post(
        author=author,
        text=text,
        image=image,
        track_title=track_title,
        track_artist=track_artist,
        track_url=track_url,
    )
    post.full_clean()
    post.save()
    return post


def update_post(
    user,
    post,
    *,
    text,
    image=_UNSET,
    track_title=_UNSET,
    track_artist=_UNSET,
    track_url=_UNSET,
):
    if not can_manage_post(user, post):
        raise PermissionDenied("Only the post author can edit it.")
    post.text = text
    if image is not _UNSET:
        post.image = image
    if track_title is not _UNSET:
        post.track_title = track_title
    if track_artist is not _UNSET:
        post.track_artist = track_artist
    if track_url is not _UNSET:
        post.track_url = track_url
    post.full_clean()
    post.save()
    return post


def can_manage_post(user, post):
    return user.is_authenticated and user.pk == post.author_id


def delete_post(user, post):
    if not can_manage_post(user, post):
        raise PermissionDenied("Only the post author can delete it.")
    post.delete()


def get_feed_for(_user) -> QuerySet[Post]:
    return (
        Post.objects.all()
        .select_related("author")
        .order_by("-created_at")
    )
