from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
    path("", views.library, name="library"),
    path("u/<str:username>/", views.user_music, name="user_music"),
    path("track/upload/", views.track_upload, name="track_upload"),
    path("track/<int:pk>/edit/", views.track_edit, name="track_edit"),
    path("track/<int:pk>/", views.track_detail, name="track_detail"),
    path("track/<int:pk>/delete/", views.track_delete, name="track_delete"),
    path("track/<int:pk>/review/", views.track_review, name="track_review"),
    path("track/<int:track_id>/like/", views.toggle_like, name="toggle_like"),
    path("album/new/", views.album_create, name="album_create"),
    path("album/<int:pk>/edit/", views.album_edit, name="album_edit"),
    path("album/<int:pk>/delete/", views.album_delete, name="album_delete"),
    path("album/<int:pk>/", views.album_detail, name="album_detail"),
    path("album/<int:pk>/review/", views.album_review, name="album_review"),
]
