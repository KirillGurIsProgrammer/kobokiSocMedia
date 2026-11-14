import re

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.feed.urls")),
    path("", include("apps.accounts.urls")),
    path("chat/", include("apps.chat.urls")),
    path("", include("apps.comments.urls")),
    path("music/", include("apps.music.urls")),
]

if settings.DEBUG or settings.SERVE_MEDIA:
    media_prefix = re.escape(settings.MEDIA_URL.lstrip("/"))
    urlpatterns += [
        re_path(
            rf"^{media_prefix}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]
