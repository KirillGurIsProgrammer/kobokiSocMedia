from django.core.exceptions import ValidationError

from .models import Follow


def can_edit_profile(user, profile):
    return user.is_authenticated and user.pk == profile.pk


def follow(user, target):
    if not user.is_authenticated:
        raise ValidationError("Authentication is required to follow users.")
    if user.pk == target.pk:
        raise ValidationError("You cannot follow yourself.")

    follow_record, _ = Follow.objects.get_or_create(
        follower=user,
        following=target,
    )
    return follow_record


def unfollow(user, target):
    if not user.is_authenticated:
        raise ValidationError("Authentication is required to unfollow users.")
    if user.pk == target.pk:
        raise ValidationError("You cannot unfollow yourself.")
    deleted, _ = Follow.objects.filter(
        follower=user,
        following=target,
    ).delete()
    return bool(deleted)


def is_following(user, target):
    return user.is_authenticated and Follow.objects.filter(
        follower=user,
        following=target,
    ).exists()
