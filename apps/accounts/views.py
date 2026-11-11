from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, render

User = get_user_model()


def profile(request, username):
    profile_user = get_object_or_404(
        User.objects.prefetch_related("posts"),
        username=username,
    )
    return render(request, "accounts/profile.html", {"profile_user": profile_user})
