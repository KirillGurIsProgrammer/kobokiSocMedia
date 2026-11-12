from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import AlbumForm, ReviewForm, TrackForm
from .models import Album, Track

User = get_user_model()


def _render_library(request, owner):
    q = request.GET.get("q", "").strip()
    return render(request, "music/track_list.html", {
        "owner": owner,
        "is_mine": owner == request.user,
        "tracks": services.search_tracks(owner, q),
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
    track = get_object_or_404(Track.objects.select_related("owner", "album"), pk=pk)
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
        "tracks": album.tracks.all(),
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
def album_review(request, pk):
    return _handle_review(request, album=get_object_or_404(Album, pk=pk))
