"""Бизнес-правила музыки. Вьюхи только вызывают эти функции."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Q

from .models import Review, Track


def search_tracks(owner, query=""):
    qs = Track.objects.filter(owner=owner).select_related("album")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return qs


def get_neighbors(track):
    """Предыдущий и следующий трек (в альбоме или среди треков без альбома)."""
    if track.album_id:
        qs = Track.objects.filter(album_id=track.album_id)
    else:
        qs = Track.objects.filter(owner_id=track.owner_id, album__isnull=True)
    prev_track = qs.filter(id__lt=track.id).order_by("-id").first()
    next_track = qs.filter(id__gt=track.id).order_by("id").first()
    return prev_track, next_track


def average_rating(obj):
    """Средний рейтинг трека или альбома (None, если отзывов нет)."""
    value = obj.reviews.aggregate(avg=Avg("rating"))["avg"]
    return round(value, 1) if value is not None else None


def ensure_owner(user, obj):
    if obj.owner_id != user.id:
        raise PermissionDenied("Это может делать только владелец")


def delete_track(user, track):
    ensure_owner(user, track)
    track.audio_file.delete(save=False)
    track.delete()


def add_review(author, rating, text, *, track=None, album=None):
    if (track is None) == (album is None):
        raise ValueError("Нужно указать ровно одну цель отзыва: трек или альбом")
    target = {"track": track} if track is not None else {"album": album}
    if Review.objects.filter(author=author, **target).exists():
        raise ValidationError("Вы уже оставили отзыв")
    review = Review(author=author, rating=rating, text=text, **target)
    review.full_clean(validate_constraints=False)
    review.save()
    return review
