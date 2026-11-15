from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_http_methods

from .forms import PostForm
from .models import Post
from .services import (
    can_manage_post,
    create_post,
    delete_post,
    get_feed_for,
    posts_with_interactions,
    update_post,
    toggle_post_like,
)


@login_required
def feed(request):
    paginator = Paginator(get_feed_for(request.user), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "feed/feed.html", {"page_obj": page_obj})


@login_required
@require_http_methods(["GET", "POST"])
def post_create(request):
    form = PostForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        create_post(request.user, **form.cleaned_data)
        return redirect("feed:feed")
    return render(request, "feed/post_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def post_edit(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("author"),
        pk=post_id,
    )
    if not can_manage_post(request.user, post):
        raise PermissionDenied

    form = PostForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=post,
    )
    if request.method == "POST" and form.is_valid():
        update_post(request.user, post, **form.cleaned_data)
        return redirect("feed:post_detail", post_id=post.pk)
    return render(request, "feed/post_form.html", {"form": form, "post": post})


def post_detail(request, post_id):
    post = get_object_or_404(
        posts_with_interactions(
            Post.objects.select_related("author"),
            request.user,
        ),
        pk=post_id,
    )
    return render(request, "feed/post_detail.html", {"post": post})


@login_required
@require_POST
def post_toggle_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    liked = toggle_post_like(post=post, user=request.user)
    like_count = post.likes.count()
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({"liked": liked, "like_count": like_count})
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("feed:post_detail", post_id=post.pk)


@login_required
@require_http_methods(["POST"])
def post_delete(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    delete_post(request.user, post)
    return redirect("feed:feed")