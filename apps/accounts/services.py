def can_edit_profile(user, profile):
    return user.is_authenticated and user.pk == profile.pk
