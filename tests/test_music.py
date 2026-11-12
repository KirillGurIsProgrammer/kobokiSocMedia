import shutil
import tempfile
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from apps.core.validators import validate_audio
from apps.music import services
from apps.music.models import Like, MusicSettings, NowPlaying, Playlist, Track

TEMP_MEDIA = tempfile.mkdtemp()


class ValidatorTests(SimpleTestCase):
    def test_audio_ok(self):
        validate_audio(SimpleUploadedFile("a.mp3", b"x"))

    def test_audio_bad_extension(self):
        with self.assertRaises(ValidationError):
            validate_audio(SimpleUploadedFile("a.exe", b"x"))

    def test_audio_too_big(self):
        with self.assertRaises(ValidationError):
            validate_audio(SimpleUploadedFile("a.mp3", b"x" * (21 * 1024 * 1024)))


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MusicTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def _track(self, owner, title="T"):
        return Track.objects.create(
            owner=owner, title=title, artist="A",
            audio_file=SimpleUploadedFile(f"{title}.mp3", b"x"),
        )

    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="pass12345")
        self.bob = User.objects.create_user(username="bob", password="pass12345")
        self.track = self._track(self.alice)

    def test_neighbors(self):
        t2 = self._track(self.alice, "T2")
        self.assertEqual(services.get_neighbors(self.track), (None, t2))
        self.assertEqual(services.get_neighbors(t2), (self.track, None))

    def test_review_only_once(self):
        services.add_review(self.bob, 5, "ok", track=self.track)
        with self.assertRaises(ValidationError):
            services.add_review(self.bob, 4, "again", track=self.track)
        self.assertEqual(services.average_rating(self.track), 5.0)

    def test_anonymous_redirected(self):
        resp = self.client.get(reverse("music:library"))
        self.assertEqual(resp.status_code, 302)

    def test_library_renders_persistent_player_and_playable_track(self):
        self.client.login(username="alice", password="pass12345")
        response = self.client.get(reverse("music:library"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-music-player')
        self.assertContains(response, f'data-track-id="{self.track.pk}"')
        self.assertContains(response, "Рекомендации")
        self.assertContains(response, "Мои треки и альбомы")
        self.assertEqual(response.content.count(b"<audio "), 1)

    def test_like_toggles_and_keeps_one_user_track_pair(self):
        liked, count = services.toggle_like(self.bob, self.track)
        self.assertTrue(liked)
        self.assertEqual(count, 1)
        self.assertEqual(Like.objects.filter(user=self.bob, track=self.track).count(), 1)

        liked, count = services.toggle_like(self.bob, self.track)
        self.assertFalse(liked)
        self.assertEqual(count, 0)
        self.assertFalse(Like.objects.filter(user=self.bob, track=self.track).exists())

    def test_like_api_returns_json(self):
        self.client.login(username="bob", password="pass12345")
        response = self.client.post(
            reverse("music:toggle_like", args=[self.track.pk]),
            data=json.dumps({"track_id": self.track.pk}),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"liked": True, "like_count": 1})

    def test_like_database_constraint_rejects_duplicate_pair(self):
        Like.objects.create(user=self.bob, track=self.track)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Like.objects.create(user=self.bob, track=self.track)

    def _playlist(self, owner, *, public=True):
        return Playlist.objects.create(
            owner=owner,
            title="Подборка",
            description="",
            is_public=public,
        )

    def test_private_playlist_is_hidden_from_other_users(self):
        playlist = self._playlist(self.alice, public=False)
        self.client.login(username="bob", password="pass12345")

        response = self.client.get(reverse("music:playlist_detail", args=[playlist.pk]))

        self.assertEqual(response.status_code, 404)

    def test_public_playlist_can_be_saved_and_unsaved(self):
        playlist = self._playlist(self.alice)

        self.assertTrue(services.toggle_saved_playlist(self.bob, playlist))
        self.assertFalse(services.toggle_saved_playlist(self.bob, playlist))
        self.assertFalse(playlist.saves.filter(user=self.bob).exists())

    def test_private_playlist_cannot_be_saved(self):
        playlist = self._playlist(self.alice, public=False)
        with self.assertRaises(PermissionDenied):
            services.toggle_saved_playlist(self.bob, playlist)

    def test_only_owner_can_change_playlist_tracks(self):
        playlist = self._playlist(self.alice)
        with self.assertRaises(PermissionDenied):
            services.add_track_to_playlist(self.bob, playlist, self.track)

    def test_playlist_track_order_and_removal(self):
        playlist = self._playlist(self.alice)
        second = self._track(self.alice, "Second")
        services.add_track_to_playlist(self.alice, playlist, self.track)
        services.add_track_to_playlist(self.alice, playlist, second)
        services.move_playlist_track(self.alice, playlist, second, "up")

        entries = list(playlist.playlist_tracks.order_by("position"))
        self.assertEqual([entry.track_id for entry in entries], [second.pk, self.track.pk])

        services.remove_track_from_playlist(self.alice, playlist, second)
        remaining = playlist.playlist_tracks.get()
        self.assertEqual((remaining.track_id, remaining.position), (self.track.pk, 0))

    def test_recommendations_prioritize_liked_artists_and_exclude_own_and_liked(self):
        self.track.artist = "Любимая группа"
        self.track.save(update_fields=("artist",))
        favorite_artist_track = self._track(self.bob, "Похожий исполнитель")
        favorite_artist_track.artist = "Любимая группа"
        favorite_artist_track.save(update_fields=("artist",))
        popular_track = self._track(self.bob, "Популярный трек")
        fallback_track = self._track(self.bob, "Свежий трек")
        Like.objects.create(user=self.alice, track=self.track)
        Like.objects.create(user=self.bob, track=popular_track)

        recommendations = services.get_recommendations(self.alice, limit=20)

        recommended_ids = [track.pk for track in recommendations]
        self.assertEqual(recommended_ids[0], favorite_artist_track.pk)
        self.assertNotIn(self.track.pk, recommended_ids)
        self.assertNotIn(self.alice.tracks.first().pk, recommended_ids)
        self.assertEqual(len(recommended_ids), len(set(recommended_ids)))
        self.assertIn(popular_track.pk, recommended_ids)
        self.assertIn(fallback_track.pk, recommended_ids)

    def test_now_playing_position_is_calculated_and_capped(self):
        state = NowPlaying.objects.create(
            user=self.alice,
            track=self.track,
            position_seconds=9,
            duration_seconds=10,
            is_playing=True,
        )
        NowPlaying.objects.filter(pk=state.pk).update(
            updated_at=timezone.now() - timedelta(seconds=5)
        )

        snapshot = services.now_playing_snapshot(self.alice, self.bob)

        self.assertEqual(snapshot["position_seconds"], 10)
        self.assertTrue(snapshot["is_listening"])

    def test_now_playing_respects_visibility_setting(self):
        NowPlaying.objects.create(user=self.alice, track=self.track, is_playing=True)
        MusicSettings.objects.create(user=self.alice, show_now_playing=False)

        self.assertEqual(services.now_playing_snapshot(self.alice, self.bob), {"visible": False})
        self.assertTrue(services.now_playing_snapshot(self.alice, self.alice)["visible"])

    def test_now_playing_api_updates_own_state(self):
        self.client.login(username="alice", password="pass12345")
        response = self.client.post(
            reverse("music:now_playing_update"),
            data=json.dumps({
                "track_id": self.track.pk,
                "position_seconds": 4.5,
                "duration_seconds": 80,
                "is_playing": True,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        state = NowPlaying.objects.get(user=self.alice)
        self.assertEqual(state.track, self.track)
        self.assertEqual(state.position_seconds, 4.5)

    def test_foreign_track_cannot_be_deleted(self):
        self.client.login(username="bob", password="pass12345")
        resp = self.client.post(reverse("music:track_delete", args=[self.track.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Track.objects.filter(pk=self.track.pk).exists())

    def test_owner_can_delete(self):
        self.client.login(username="alice", password="pass12345")
        resp = self.client.post(reverse("music:track_delete", args=[self.track.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Track.objects.filter(pk=self.track.pk).exists())
