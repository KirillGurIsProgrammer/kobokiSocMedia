from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.feed.urls")),
    path("", include("apps.accounts.urls")),
    path("chat/", include("apps.chat.urls")),
    path("", include("apps.comments.urls")),
    path("music/", include("apps.music.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
