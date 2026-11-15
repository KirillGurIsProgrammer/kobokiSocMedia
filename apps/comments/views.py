from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.feed.models import Post

from .forms import CommentForm
from .models import Comment
from .services import add_comment, delete_comment


@login_required
def add_post_comment(request, post_id):
    if request.method != "POST":
        return redirect("feed:post_detail", post_id=post_id)
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    wants_json = "application/json" in request.headers.get("Accept", "")
    if form.is_valid():
        try:
            comment = add_comment(
                post=post,
                author=request.user,
                text=form.cleaned_data["text"],
            )
        except ValidationError as error:
            if wants_json:
                return JsonResponse({"error": error.message}, status=400)
            messages.error(request, error.message)
        else:
            if wants_json:
                return JsonResponse(
                    {
                        "id": comment.pk,
                        "author": comment.author.username,
                        "author_url": reverse(
                            "accounts:profile",
                            kwargs={"username": comment.author.username},
                        ),
                        "text": comment.text,
                        "comment_count": post.comments.count(),
                    },
                    status=201,
                )
    elif wants_json:
        return JsonResponse(
            {"error": "Комментарий должен содержать от 1 до 1000 символов."},
            status=400,
        )
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("feed:post_detail", post_id=post.pk)


@login_required
def delete(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.method == "POST":
        try:
            delete_comment(comment=comment, user=request.user)
        except PermissionDenied:
            raise
    return redirect("feed:post_detail", post_id=comment.post_id)
