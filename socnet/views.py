from django.shortcuts import render

from apps.feed.models import Post


def home(request):
    posts = Post.objects.select_related("author").order_by("-created_at")[:10]
    return render(request, "home.html", {"posts": posts})
