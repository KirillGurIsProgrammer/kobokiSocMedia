import shutil
import tempfile
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.core.validators import validate_audio
from apps.music import services
from apps.music.models import Like, Track

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
