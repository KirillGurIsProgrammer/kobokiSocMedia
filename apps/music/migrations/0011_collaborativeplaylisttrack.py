from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_collaborative_tracks(apps, schema_editor):
    CollaborativePlaylist = apps.get_model("music", "CollaborativePlaylist")
    CollaborativePlaylistMember = apps.get_model(
        "music", "CollaborativePlaylistMember"
    )
    CollaborativePlaylistTrack = apps.get_model(
        "music", "CollaborativePlaylistTrack"
    )
    Like = apps.get_model("music", "Like")

    for playlist in CollaborativePlaylist.objects.all().iterator():
        member_ids = list(
            CollaborativePlaylistMember.objects.filter(playlist_id=playlist.pk)
            .order_by("joined_at", "pk")
            .values_list("user_id", flat=True)
        )
        likes_by_member = {member_id: [] for member_id in member_ids}
        for user_id, track_id in Like.objects.filter(
            user_id__in=member_ids
        ).order_by("user_id", "-created_at", "-pk").values_list(
            "user_id", "track_id"
        ):
            likes_by_member[user_id].append(track_id)

        positions = dict.fromkeys(member_ids, 0)
        seen = set()
        entries = []
        while len(entries) < 40:
            added = False
            for member_id in member_ids:
                member_likes = likes_by_member[member_id]
                position = positions[member_id]
                while position < len(member_likes) and member_likes[position] in seen:
                    position += 1
                positions[member_id] = position
                if position < len(member_likes):
                    track_id = member_likes[position]
                    positions[member_id] += 1
                    seen.add(track_id)
                    entries.append(
                        CollaborativePlaylistTrack(
                            playlist_id=playlist.pk,
                            track_id=track_id,
                            added_by_id=member_id,
                            position=len(entries),
                        )
                    )
                    added = True
                    if len(entries) == 40:
                        break
            if not added:
                break
        CollaborativePlaylistTrack.objects.bulk_create(entries)


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0010_collaborativeplaylist_collaborativeplaylistinvite_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CollaborativePlaylistTrack",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.PositiveIntegerField(default=0)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="collaborative_playlist_tracks_added",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "playlist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="track_entries",
                        to="music.collaborativeplaylist",
                    ),
                ),
                (
                    "track",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="collaborative_playlist_entries",
                        to="music.track",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "pk"),
            },
        ),
        migrations.AddConstraint(
            model_name="collaborativeplaylisttrack",
            constraint=models.UniqueConstraint(
                fields=("playlist", "track"),
                name="unique_track_per_collaborative_playlist",
            ),
        ),
        migrations.RunPython(seed_collaborative_tracks, migrations.RunPython.noop),
    ]
