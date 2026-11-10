from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxLengthValidator
from django.db import models

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