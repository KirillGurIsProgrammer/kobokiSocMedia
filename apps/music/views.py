from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import AlbumForm, PlaylistForm, PlaylistTrackForm, ReviewForm, TrackForm
from .models import Album, PlaylistTrack, SavedPlaylist, Track

User = get_user_model()


def _render_library(request, owner):
    q = request.GET.get("q", "").strip()
    return render(request, "music/track_list.html", {
        "owner": owner,
        "is_mine": owner == request.user,
        "tracks": services.search_tracks(owner, q, user=request.user),
        "discover_tracks": services.get_discover_tracks(request.user, q),
        "albums": owner.albums.all(),
        "q": q,
    })


@login_required
def library(request):
    return _render_library(request, request.user)


@login_required
def user_music(request, username):
    owner = get_object_or_404(User, username=username)
    return _render_library(request, owner)


@login_required
def track_upload(request):
    if request.method == "POST":
        form = TrackForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            track = services.create_track(
                request.user,
                title=data["title"],
                artist=data["artist"],
                album=data["album"],
                audio_file=data["audio_file"],
            )
            messages.success(request, "Трек загружен.")
            return redirect(track)
    else:
        form = TrackForm(user=request.user)
    return render(request, "music/track_form.html", {"form": form})


@login_required
def track_edit(request, pk):
    track = get_object_or_404(Track, pk=pk)
    services.ensure_owner(request.user, track)
    if request.method == "POST":
        form = TrackForm(request.POST, request.FILES, instance=track, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            services.update_track(
                request.user,
                track,
                title=data["title"],
                artist=data["artist"],
                album=data["album"],
                audio_file=data.get("audio_file"),
            )
            messages.success(request, "Изменения трека сохранены.")
            return redirect(track)
    else:
        form = TrackForm(instance=track, user=request.user)
    return render(request, "music/track_form.html", {"form": form, "track": track})


@login_required
def track_detail(request, pk):
    track = get_object_or_404(
        services.with_like_data(
            Track.objects.select_related("owner", "album"), request.user
        ),
        pk=pk,
    )
    prev_track, next_track = services.get_neighbors(track)
    return render(request, "music/track_detail.html", {
        "track": track,
        "prev_track": prev_track,
        "next_track": next_track,
        "reviews": track.reviews.select_related("author"),
        "rating": services.average_rating(track),
        "review_form": ReviewForm(),
        "is_owner": track.owner_id == request.user.id,
    })


@login_required
@require_POST
def track_delete(request, pk):
    track = get_object_or_404(Track, pk=pk)
    services.delete_track(request.user, track)
    messages.success(request, "Трек удалён.")
    return redirect("music:library")


@login_required
def album_create(request):
    if request.method == "POST":
        form = AlbumForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            album = services.create_album(
                request.user, title=data["title"], cover=data.get("cover")
            )
            messages.success(request, "Альбом создан.")
            return redirect(album)
    else:
        form = AlbumForm()
    return render(request, "music/album_form.html", {"form": form})


@login_required
def album_edit(request, pk):
    album = get_object_or_404(Album, pk=pk)
    services.ensure_owner(request.user, album)
    if request.method == "POST":
        form = AlbumForm(request.POST, request.FILES, instance=album)
        if form.is_valid():
            data = form.cleaned_data
            services.update_album(
                request.user, album, title=data["title"], cover=data.get("cover")
            )
            messages.success(request, "Изменения альбома сохранены.")
            return redirect(album)
    else:
        form = AlbumForm(instance=album)
    return render(request, "music/album_form.html", {"form": form, "album": album})


@login_required
@require_POST
def album_delete(request, pk):
    album = get_object_or_404(Album, pk=pk)
    services.delete_album(request.user, album)
    messages.success(request, "Альбом удалён.")
    return redirect("music:library")


@login_required
def album_detail(request, pk):
    album = get_object_or_404(Album.objects.select_related("owner"), pk=pk)
    return render(request, "music/album_detail.html", {
        "album": album,
        "tracks": services.with_like_data(
            album.tracks.select_related("owner", "album"), request.user
        ),
        "reviews": album.reviews.select_related("author"),
        "rating": services.average_rating(album),
        "review_form": ReviewForm(),
        "is_owner": album.owner_id == request.user.id,
    })


def _handle_review(request, *, track=None, album=None):
    form = ReviewForm(request.POST)
    if form.is_valid():
        try:
            services.add_review(
                request.user,
                form.cleaned_data["rating"],
                form.cleaned_data["text"],
                track=track,
                album=album,
            )
            messages.success(request, "Отзыв отправлен.")
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
    else:
        messages.error(request, "Проверьте оценку и текст отзыва.")
    return redirect(track or album)


@login_required
@require_POST
def track_review(request, pk):
    return _handle_review(request, track=get_object_or_404(Track, pk=pk))


@login_required
@require_POST
def toggle_like(request, track_id):
    track = get_object_or_404(Track, pk=track_id)
    liked, like_count = services.toggle_like(request.user, track)
    if request.headers.get("Accept", "").find("application/json") >= 0:
        return JsonResponse({"liked": liked, "like_count": like_count})
    return redirect(track.get_absolute_url())


def _viewable_playlist_or_404(user, playlist_id):
    playlist = services.get_viewable_playlist(user, playlist_id)
    if playlist is None:
        raise Http404
    return playlist


def _owned_playlist_or_404(user, playlist_id):
    playlist = services.get_owned_playlist(user, playlist_id)
    if playlist is None:
        raise Http404
    return playlist


@login_required
def playlists(request):
    return render(request, "music/playlist_list.html", {
        "my_playlists": services.list_user_playlists(request.user),
        "saved_playlists": services.list_saved_playlists(request.user),
        "public_playlists": services.list_public_playlists(request.user),
    })


@login_required
def liked_tracks(request):
    return render(request, "music/liked_tracks.html", {
        "tracks": services.list_liked_tracks(request.user),
    })


@login_required
def playlist_create(request):
    if request.method == "POST":
        form = PlaylistForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            playlist = services.create_playlist(
                request.user,
                title=data["title"],
                description=data["description"],
                cover=data.get("cover"),
                is_public=data["is_public"],
            )
            return redirect(playlist)
    else:
        form = PlaylistForm()
    return render(request, "music/playlist_form.html", {"form": form})


@login_required
def playlist_edit(request, playlist_id):
    playlist = _owned_playlist_or_404(request.user, playlist_id)
    if request.method == "POST":
        form = PlaylistForm(request.POST, request.FILES, instance=playlist)
        if form.is_valid():
            data = form.cleaned_data
            services.update_playlist(
                request.user,
                playlist,
                title=data["title"],
                description=data["description"],
                cover=data.get("cover"),
                is_public=data["is_public"],
            )
            return redirect(playlist)
    else:
        form = PlaylistForm(instance=playlist)
    return render(request, "music/playlist_form.html", {"form": form, "playlist": playlist})


@login_required
@require_POST
def playlist_delete(request, playlist_id):
    playlist = _owned_playlist_or_404(request.user, playlist_id)
    services.delete_playlist(request.user, playlist)
    return redirect("music:playlists")


@login_required
def playlist_detail(request, playlist_id):
    playlist = _viewable_playlist_or_404(request.user, playlist_id)
    entries = services.get_playlist_entries(request.user, playlist)
    return render(request, "music/playlist_detail.html", {
        "playlist": playlist,
        "entries": entries,
        "is_owner": playlist.owner_id == request.user.pk,
        "is_saved": SavedPlaylist.objects.filter(user=request.user, playlist=playlist).exists(),
        "add_track_form": PlaylistTrackForm(),
    })


@login_required
@require_POST
def playlist_add_track(request, playlist_id):
    playlist = _owned_playlist_or_404(request.user, playlist_id)
    form = PlaylistTrackForm(request.POST)
    if form.is_valid():
        try:
            services.add_track_to_playlist(request.user, playlist, form.cleaned_data["track"])
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
    else:
        messages.error(request, "Выберите трек для добавления.")
    return redirect(playlist)


@login_required
@require_POST
def playlist_remove_track(request, playlist_id, track_id):
    playlist = _owned_playlist_or_404(request.user, playlist_id)
    track = get_object_or_404(Track, pk=track_id)
    try:
        services.remove_track_from_playlist(request.user, playlist, track)
    except PlaylistTrack.DoesNotExist:
        raise Http404
    return redirect(playlist)


@login_required
@require_POST
def playlist_move_track(request, playlist_id, track_id, direction):
    playlist = _owned_playlist_or_404(request.user, playlist_id)
    track = get_object_or_404(Track, pk=track_id)
    try:
        services.move_playlist_track(request.user, playlist, track, direction)
    except PlaylistTrack.DoesNotExist:
        raise Http404
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    return redirect(playlist)


@login_required
@require_POST
def playlist_toggle_saved(request, playlist_id):
    playlist = _viewable_playlist_or_404(request.user, playlist_id)
    try:
        is_saved = services.toggle_saved_playlist(request.user, playlist)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Плейлист сохранён." if is_saved else "Плейлист удалён из сохранённых.")
    return redirect(playlist)


@login_required
@require_POST
def album_review(request, pk):
    return _handle_review(request, album=get_object_or_404(Album, pk=pk))
