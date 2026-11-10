from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ProfileForm, RegistrationForm
from .models import User
from .services import can_edit_profile


@require_http_methods(["GET", "POST"])
def register(request):
    form = RegistrationForm(
        request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("accounts:profile", username=user.username)
    return render(request, "accounts/register.html", {"form": form})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    return render(request, "accounts/profile.html", {"profile_user": profile_user})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not can_edit_profile(request.user, profile_user):
        raise PermissionDenied

    form = ProfileForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=profile_user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:profile", username=profile_user.username)
    return render(
        request,
        "accounts/profile_edit.html",
        {"form": form, "profile_user": profile_user},
    )