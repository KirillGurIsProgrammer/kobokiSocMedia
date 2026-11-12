from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
    path("", views.library, name="library"),
    path("liked/", views.liked_tracks, name="liked_tracks"),
    path("settings/", views.music_settings, name="settings"),
    path("api/now-playing/", views.now_playing_update, name="now_playing_update"),
    path("api/now-playing/<str:username>/", views.now_playing_detail, name="now_playing_detail"),
    path("api/listen-along/<str:username>/join/", views.listen_along_join, name="listen_along_join"),
    path("api/listen-along/leave/", views.listen_along_leave, name="listen_along_leave"),
    path("u/<str:username>/", views.user_music, name="user_music"),
    path("track/upload/", views.track_upload, name="track_upload"),
    path("track/<int:pk>/edit/", views.track_edit, name="track_edit"),
    path("track/<int:pk>/", views.track_detail, name="track_detail"),
    path("track/<int:pk>/delete/", views.track_delete, name="track_delete"),
    path("track/<int:pk>/review/", views.track_review, name="track_review"),
    path("track/<int:track_id>/like/", views.toggle_like, name="toggle_like"),
    path("playlists/", views.playlists, name="playlists"),
    path("playlists/new/", views.playlist_create, name="playlist_create"),
    path("playlist/<int:playlist_id>/", views.playlist_detail, name="playlist_detail"),
    path("playlist/<int:playlist_id>/edit/", views.playlist_edit, name="playlist_edit"),
    path("playlist/<int:playlist_id>/delete/", views.playlist_delete, name="playlist_delete"),
    path("playlist/<int:playlist_id>/save/", views.playlist_toggle_saved, name="playlist_toggle_saved"),
    path("playlist/<int:playlist_id>/tracks/add/", views.playlist_add_track, name="playlist_add_track"),
    path("playlist/<int:playlist_id>/tracks/<int:track_id>/remove/", views.playlist_remove_track, name="playlist_remove_track"),
    path("playlist/<int:playlist_id>/tracks/<int:track_id>/move/<str:direction>/", views.playlist_move_track, name="playlist_move_track"),
    path("album/new/", views.album_create, name="album_create"),
    path("album/<int:pk>/edit/", views.album_edit, name="album_edit"),
    path("album/<int:pk>/delete/", views.album_delete, name="album_delete"),
    path("album/<int:pk>/", views.album_detail, name="album_detail"),
    path("album/<int:pk>/review/", views.album_review, name="album_review"),
]
