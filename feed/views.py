from django.shortcuts import get_object_or_404, render

from .models import Post


def post_detail(request, post_id):
    post = get_object_or_404(Post.objects.select_related("author").prefetch_related("comments__author"), pk=post_id)
    return render(request, "feed/post_detail.html", {"post": post})
