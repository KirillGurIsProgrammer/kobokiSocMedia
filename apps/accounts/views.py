from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from apps.feed.services import posts_with_interactions

from .forms import ProfileForm, RegistrationForm
from .models import Follow
from .services import can_edit_profile, follow, is_following, unfollow


User = get_user_model()


@login_required
def user_directory(request):
    query = request.GET.get("q", "").strip()
    users = User.objects.exclude(pk=request.user.pk).annotate(
        is_following=Exists(
            Follow.objects.filter(
                follower=request.user,
                following_id=OuterRef("pk"),
            )
        )
    )
    if query:
        users = users.filter(Q(username__icontains=query) | Q(bio__icontains=query))

    page_obj = Paginator(users.order_by("username"), 20).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "accounts/user_directory.html",
        {"page_obj": page_obj, "query": query},
    )


def _follow_redirect(request, target):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("accounts:profile", username=target.username)


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
    context = {
        "profile_user": profile_user,
        "posts": posts_with_interactions(
            profile_user.posts.select_related("author"),
            request.user,
        ),
        "followers_count": profile_user.followers.count(),
        "following_count": profile_user.following.count(),
        "is_following": is_following(request.user, profile_user),
    }
    return render(request, "accounts/profile.html", context)


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


@login_required
@require_http_methods(["POST"])
def follow_user(request, username):
    target = get_object_or_404(User, username=username)
    try:
        follow(request.user, target)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    return _follow_redirect(request, target)


@login_required
@require_http_methods(["POST"])
def unfollow_user(request, username):
    target = get_object_or_404(User, username=username)
    try:
        unfollow(request.user, target)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    return _follow_redirect(request, target)