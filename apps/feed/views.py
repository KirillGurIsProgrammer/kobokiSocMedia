from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PostForm
from .models import Post
from .services import (
    can_manage_post,
    create_post,
    delete_post,
    get_feed_for,
    update_post,
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
        Post.objects.select_related("author"),
        pk=post_id,
    )
    return render(request, "feed/post_detail.html", {"post": post})


@login_required
@require_http_methods(["POST"])
def post_delete(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    delete_post(request.user, post)
    return redirect("feed:feed")