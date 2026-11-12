from django import template
from django.urls import reverse
from math import floor

from apps.music import services

register = template.Library()


@register.inclusion_tag("music/_now_playing.html", takes_context=True)
def now_playing_card(context, profile_user):
    viewer = context.get("user")
    snapshot = services.now_playing_snapshot(profile_user, viewer)
    track = snapshot.get("track")
    playlist = snapshot.get("playlist")
    source = None
    if track is not None:
        if playlist is not None:
            source = {"label": playlist.title, "url": playlist.get_absolute_url()}
        elif track.album_id:
            source = {
                "label": f"из альбома «{track.album.title}»",
                "url": track.album.get_absolute_url(),
            }
        else:
            source = {"label": "из библиотеки", "url": None}
    position = snapshot.get("position_seconds", 0)
    duration = snapshot.get("duration_seconds", 0)
    snapshot["position_label"] = _format_time(position)
    snapshot["duration_label"] = _format_time(duration)
    snapshot["progress_percent"] = min(100, int(position / duration * 100)) if duration else 0
    return {
        "profile_user": profile_user,
        "snapshot": snapshot,
        "source": source,
        "endpoint": reverse("music:now_playing_detail", args=[profile_user.username]),
    }


def _format_time(seconds):
    seconds = max(0, floor(seconds or 0))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
