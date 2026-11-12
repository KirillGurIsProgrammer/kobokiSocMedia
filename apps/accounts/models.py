from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import F, Q

from .validators import validate_profile_image


class User(AbstractUser):
    bio = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(300)],
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        validators=[validate_profile_image],
    )


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("follower", "following"),
                name="unique_follow_pair",
            ),
            models.CheckConstraint(
                condition=~Q(follower=F("following")),
                name="cannot_follow_self",
            ),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.follower} follows {self.following}"