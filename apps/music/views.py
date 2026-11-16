from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import services
from .forms import (
    AlbumForm,
    CollaborativePlaylistForm,
    MusicSettingsForm,
    PlaylistForm,
    PlaylistTrackForm,
    ReviewForm,
    TrackForm,
    TrackUploadForm,
)
from .models import Album, CollaborativePlaylist, CollaborativePlaylistInvite, Like, PlaylistTrack, SavedPlaylist, Tag, Track

User = get_user_model()


def _render_library(request, owner):
    q = request.GET.get("q", "").strip()
    recent_tracks = services.with_like_data(
        Track.objects.filter(owner=owner).select_related("owner", "album"), request.user
    ).order_by("-uploaded_at", "-pk")
    if q:
        recent_tracks = recent_tracks.filter(Q(title__icontains=q) | Q(artist__icontains=q))
    return render(request, "music/track_list.html", {
        "owner": owner,
        "is_mine": owner == request.user,
        "tracks": services.search_tracks(owner, q, user=request.user),
        "discover_tracks": services.get_discover_tracks(request.user, q),
        "recent_tracks": recent_tracks[:5],
        "my_playlists": services.list_user_playlists(request.user)[:3] if owner == request.user else [],
        "show_track_menu": owner == request.user,
        "albums": owner.albums.annotate(track_count=Count("tracks")),
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
    if request.method == "POST" and request.FILES.get("audio_file"):
        form = TrackForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            track = services.create_track(
                request.user,
                title=data["title"],
                artist=data["artist"],
                album=data["album"],
                audio_file=data["audio_file"],
                cover=data.get("cover"),
                tags=data["tags"],
            )
            messages.success(request, "Трек загружен.")
            return redirect(track)
        return render(
            request,
            "music/track_form.html",
            {
                "form": form,
                "legacy_upload": True,
                "tag_suggestions": Tag.objects.values_list("name", flat=True),
            },
        )

    if request.method == "POST":
        form = TrackUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            album = form.cleaned_data["album"]
            uploads = []
            for index, audio_file in enumerate(form.cleaned_data["audio_files"]):
                parsed_artist, parsed_title = services.parse_track_filename(audio_file.name)
                title = request.POST.get(f"title_{index}", "").strip() or parsed_title
                artist = request.POST.get(f"artist_{index}", "").strip() or parsed_artist
                try:
                    tags = services.normalize_tag_names(request.POST.get(f"tags_{index}", ""))
                except ValidationError as error:
                    messages.error(request, "; ".join(error.messages))
                    return render(
                        request,
                        "music/track_form.html",
                        {
                            "form": form,
                            "tag_suggestions": Tag.objects.values_list("name", flat=True),
                        },
                    )
                candidate = Track(
                    owner=request.user,
                    title=title,
                    artist=artist,
                    album=album,
                    audio_file=audio_file,
                    cover=request.FILES.get(f"cover_{index}"),
                )
                try:
                    candidate.full_clean()
                except ValidationError as error:
                    messages.error(request, "; ".join(error.messages))
                    return render(request, "music/track_form.html", {
                        "form": form,
                        "tag_suggestions": Tag.objects.values_list("name", flat=True),
                    })
                uploads.append((title, artist, audio_file, candidate.cover, tags))

            with transaction.atomic():
                for title, artist, audio_file, cover, tags in uploads:
                    services.create_track(
                        request.user,
                        title=title,
                        artist=artist,
                        album=album,
                        audio_file=audio_file,
                        cover=cover,
                        tags=tags,
                    )
            messages.success(request, f"Загружено треков: {len(uploads)}.")
            return redirect("music:library")
    else:
        form = TrackUploadForm(user=request.user)
    return render(request, "music/track_form.html", {
        "form": form,
        "tag_suggestions": Tag.objects.values_list("name", flat=True),
    })


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
                cover=data.get("cover"),
                tags=data["tags"],
            )
            messages.success(request, "Изменения трека сохранены.")
            return redirect(track)
    else:
        form = TrackForm(instance=track, user=request.user)
    return render(request, "music/track_form.html", {
        "form": form,
        "track": track,
        "tag_suggestions": Tag.objects.values_list("name", flat=True),
    })


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
        "collaborative_playlists": CollaborativePlaylist.objects.filter(memberships__user=request.user).select_related("creator").distinct(),
        "collaborative_invites": CollaborativePlaylistInvite.objects.filter(user=request.user, status=CollaborativePlaylistInvite.PENDING).select_related("playlist", "playlist__creator"),
        "collaborative_form": CollaborativePlaylistForm(user=request.user),
    })


@login_required
def collaborative_playlist_create(request):
    if request.method == "POST":
        form = CollaborativePlaylistForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                playlist = services.create_collaborative_playlist(
                    request.user,
                    title=form.cleaned_data["title"],
                    invitees=form.cleaned_data["invitees"],
                )
            except (ValidationError, PermissionDenied) as error:
                messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
            else:
                messages.success(request, "Совместный плейлист создан. Приглашения отправлены.")
                return redirect("music:collaborative_playlist_detail", playlist.pk)
    else:
        form = CollaborativePlaylistForm(user=request.user)
    return render(request, "music/collaborative_playlist_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def collaborative_playlist_detail(request, playlist_id):
    playlist = get_object_or_404(CollaborativePlaylist.objects.select_related("creator"), pk=playlist_id)
    try:
        tracks = services.get_collaborative_playlist_tracks(request.user, playlist)
    except PermissionDenied:
        raise Http404
    form = PlaylistTrackForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            added = services.add_collaborative_playlist_track(
                request.user,
                playlist,
                form.cleaned_data["track"],
            )
        except PermissionDenied:
            raise Http404
        except ValidationError as error:
            form.add_error("track", error)
        else:
            if added:
                messages.success(request, "Трек добавлен.")
            else:
                messages.info(request, "Этот трек уже есть в плейлисте.")
            return redirect("music:collaborative_playlist_detail", playlist.pk)
    track_data = {
        track.pk: track for track in services.with_like_data(
            Track.objects.filter(pk__in=[item.pk for item in tracks]).select_related("owner", "album"),
            request.user,
        )
    }
    for track in tracks:
        annotated = track_data[track.pk]
        track.liked_by_user = annotated.liked_by_user
        track.like_count = annotated.like_count
    return render(request, "music/collaborative_playlist_detail.html", {
        "playlist": playlist,
        "tracks": tracks,
        "track_form": form,
        "is_creator": playlist.creator_id == request.user.pk,
        "members": playlist.memberships.select_related("user").order_by("joined_at"),
    })


@login_required
@require_POST
def collaborative_invite_respond(request, invite_id, response):
    if response not in {"accept", "decline"}:
        raise Http404
    invite = get_object_or_404(CollaborativePlaylistInvite.objects.select_related("playlist"), pk=invite_id)
    try:
        services.respond_collaborative_invite(request.user, invite, accept=response == "accept")
    except PermissionDenied:
        raise Http404
    return redirect("music:collaborative_playlist_detail", invite.playlist_id) if response == "accept" else redirect("music:playlists")


@login_required
@require_POST
def collaborative_playlist_leave(request, playlist_id):
    playlist = get_object_or_404(CollaborativePlaylist, pk=playlist_id)
    try:
        services.leave_collaborative_playlist(request.user, playlist)
    except (PermissionDenied, ValidationError):
        raise Http404
    messages.success(request, "Вы вышли из плейлиста.")
    return redirect("music:playlists")


@login_required
@require_POST
def collaborative_playlist_delete(request, playlist_id):
    playlist = get_object_or_404(CollaborativePlaylist, pk=playlist_id)
    try:
        services.delete_collaborative_playlist(request.user, playlist)
    except PermissionDenied:
        raise Http404
    messages.success(request, "Совместный плейлист удалён.")
    return redirect("music:playlists")


@login_required
@require_POST
def collaborative_playlist_remove_track(request, playlist_id, track_id):
    playlist = get_object_or_404(CollaborativePlaylist, pk=playlist_id)
    track = get_object_or_404(Track, pk=track_id)
    try:
        removed = services.remove_collaborative_playlist_track(
            request.user,
            playlist,
            track,
        )
    except PermissionDenied:
        raise Http404
    if removed:
        messages.success(request, "Трек удалён из совместного плейлиста.")
    return redirect("music:collaborative_playlist_detail", playlist.pk)


@login_required
def liked_tracks(request):
    return render(request, "music/liked_tracks.html", {
        "tracks": services.list_liked_tracks(request.user),
    })


@login_required
def tag_detail(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    tracks = services.with_like_data(
        Track.objects.filter(tags=tag)
        .select_related("owner", "album")
        .order_by("-uploaded_at", "-pk"),
        request.user,
    )
    return render(request, "music/tag_detail.html", {"tag": tag, "tracks": tracks})


@login_required
def radio(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return render(request, "music/radio.html", {"tag": tag})


@login_required
@require_GET
def radio_tracks_api(request):
    slug = request.GET.get("tag", "").strip()
    if not slug:
        return JsonResponse({"error": "Укажите тег радио."}, status=400)
    tag = get_object_or_404(Tag, slug=slug)
    recent_by_tag = request.session.get("music_radio_recent", {})
    if not isinstance(recent_by_tag, dict):
        recent_by_tag = {}
    recent_ids = recent_by_tag.get(tag.slug, [])
    tracks = services.get_radio_tracks(request.user, tag, limit=10, exclude_ids=recent_ids)
    recent_by_tag[tag.slug] = list(
        dict.fromkeys([track.pk for track in tracks] + recent_ids)
    )[:50]
    request.session["music_radio_recent"] = recent_by_tag
    return JsonResponse({
        "tag": tag.slug,
        "tracks": [
            {
                "id": track.pk,
                "url": track.audio_file.url,
                "title": track.title,
                "artist": track.artist,
                "cover": (
                    track.cover.url if track.cover
                    else track.album.cover.url if track.album and track.album.cover
                    else ""
                ),
                "liked": track.liked_by_user,
                "likeCount": track.like_count,
            }
            for track in tracks
        ],
    })


@login_required
@require_GET
def track_search_api(request):
    query = request.GET.get("q", "").strip()
    tracks = Track.objects.all()
    if query:
        tracks = tracks.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    tracks = tracks.order_by("title", "artist", "pk")[:20]
    return JsonResponse({
        "results": [
            {"id": track.pk, "title": track.title, "artist": track.artist}
            for track in tracks
        ],
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
def music_settings(request):
    settings = services.get_music_settings(request.user)
    if request.method == "POST":
        form = MusicSettingsForm(request.POST)
        if form.is_valid():
            services.update_music_settings(
                request.user,
                show_now_playing=form.cleaned_data["show_now_playing"],
                allow_join=form.cleaned_data["allow_join"],
            )
            messages.success(request, "Настройки музыки сохранены.")
            return redirect("music:settings")
    else:
        form = MusicSettingsForm(initial={
            "show_now_playing": settings.show_now_playing,
            "allow_join": settings.allow_join,
        })
    return render(request, "music/settings.html", {"form": form})


@login_required
@require_POST
def now_playing_update(request):
    try:
        if request.content_type == "application/json":
            payload = json.loads(request.body or b"{}")
        else:
            payload = request.POST
        state = services.save_now_playing(
            request.user,
            track_id=payload.get("track_id"),
            playlist_id=payload.get("playlist_id"),
            position_seconds=payload.get("position_seconds", 0),
            duration_seconds=payload.get("duration_seconds", 0),
            is_playing=(payload.get("is_playing") is True or payload.get("is_playing") == "true"),
        )
    except (json.JSONDecodeError, TypeError, AttributeError, ValidationError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({
        "ok": True,
        "updated_at": state.updated_at.isoformat(),
        "listener_count": services.active_listener_count(request.user),
    })


@login_required
def now_playing_detail(request, username):
    subject = get_object_or_404(User, username=username)
    snapshot = services.now_playing_snapshot(subject, request.user)
    if not snapshot.get("visible"):
        return JsonResponse({"visible": False})
    track = snapshot.get("track")
    playlist = snapshot.get("playlist")
    data = {
        "visible": True,
        "is_listening": snapshot["is_listening"],
        "last_seen_minutes": snapshot["last_seen_minutes"],
    }
    if track is not None:
        data.update({
            "is_playing": snapshot["is_playing"],
            "track": {"title": track.title, "artist": track.artist},
            "track_id": track.pk,
            "audio_url": track.audio_file.url,
            "cover_url": (
                playlist.cover.url if playlist and playlist.cover
                else track.cover.url if track.cover
                else track.album.cover.url if track.album_id and track.album.cover
                else None
            ),
            "playlist_id": playlist.pk if playlist else None,
            "position_seconds": snapshot["position_seconds"],
            "duration_seconds": snapshot["duration_seconds"],
            "updated_at": snapshot["updated_at"].isoformat(),
            "source": (
                {"label": playlist.title, "url": playlist.get_absolute_url()}
                if playlist else
                {"label": f"из альбома «{track.album.title}»", "url": track.album.get_absolute_url()}
                if track.album_id else
                {"label": "из библиотеки", "url": None}
            ),
        })
    data["listener_count"] = snapshot.get("listener_count", 0)
    return JsonResponse(data)


@login_required
@require_POST
def listen_along_join(request, username):
    host = get_object_or_404(User, username=username)
    try:
        services.join_session(request.user, host)
    except ValidationError as error:
        return JsonResponse({"error": "; ".join(error.messages)}, status=400)
    except PermissionDenied as error:
        return JsonResponse({"error": str(error)}, status=403)
    return JsonResponse({
        "ok": True,
        "host": host.username,
        "endpoint": reverse("music:now_playing_detail", args=[host.username]),
        "leave_url": reverse("music:listen_along_leave"),
    })


@login_required
@require_POST
def listen_along_leave(request):
    services.leave_session(request.user)
    if request.headers.get("Accept", "").find("application/json") >= 0:
        return JsonResponse({"ok": True})
    return redirect("music:library")


@login_required
@require_POST
def album_review(request, pk):
    return _handle_review(request, album=get_object_or_404(Album, pk=pk))
