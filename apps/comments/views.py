from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect

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
    if form.is_valid():
        try:
            add_comment(post=post, author=request.user, text=form.cleaned_data["text"])
        except ValidationError as error:
            messages.error(request, error.message)
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
