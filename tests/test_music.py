import shutil
import tempfile
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from apps.accounts.models import Follow
from django.urls import reverse

from apps.core.validators import validate_audio
from apps.music import services
from apps.music.models import CollaborativePlaylist, CollaborativePlaylistInvite, CollaborativePlaylistMember, Like, ListenAlong, MusicSettings, NowPlaying, Playlist, Track

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


class TrackFilenameParserTests(SimpleTestCase):
    def assert_parsed(self, filename, expected):
        self.assertEqual(services.parse_track_filename(filename), expected)

    def test_hyphen_separator(self):
        self.assert_parsed("Artist - Track.mp3", ("Artist", "Track"))

    def test_en_dash_separator(self):
        self.assert_parsed("Artist – Track.wav", ("Artist", "Track"))

    def test_em_dash_separator(self):
        self.assert_parsed("Artist — Track.ogg", ("Artist", "Track"))

    def test_underscores_become_spaces(self):
        self.assert_parsed("Northern_Lights - Blue_Room.mp3", ("Northern Lights", "Blue Room"))

    def test_leading_number_with_period(self):
        self.assert_parsed("01. Artist - Track.mp3", ("Artist", "Track"))

    def test_leading_number_with_hyphen(self):
        self.assert_parsed("01 - Artist - Track.mp3", ("Artist", "Track"))

    def test_leading_number_without_space(self):
        self.assert_parsed("07—Artist — Track.flac", ("Artist", "Track"))

    def test_official_video_annotation_is_removed(self):
        self.assert_parsed("Artist - Track (Official Video).mp3", ("Artist", "Track"))

    def test_bracketed_bitrate_is_removed(self):
        self.assert_parsed("Artist - Track [320kbps].mp3", ("Artist", "Track"))

    def test_bitrate_annotation_with_spaces_is_removed(self):
        self.assert_parsed("Artist - Track (320 kbps, HQ).mp3", ("Artist", "Track"))

    def test_protocol_url_is_removed(self):
        self.assert_parsed("Artist - Track https://example.com/watch.mp3", ("Artist", "Track"))

    def test_www_address_is_removed(self):
        self.assert_parsed("Artist - Track www.example.org/file.mp3", ("Artist", "Track"))

    def test_russian_names(self):
        self.assert_parsed("Привычка — Ночной город.mp3", ("Привычка", "Ночной город"))

    def test_russian_underscores(self):
        self.assert_parsed("Кино_Группа - Пачка_сигарет.mp3", ("Кино Группа", "Пачка сигарет"))

    def test_missing_artist(self):
        self.assert_parsed("Только название.mp3", ("", "Только название"))

    def test_feat_remains_in_title(self):
        self.assert_parsed("Artist - Track feat. Guest.mp3", ("Artist", "Track feat. Guest"))

    def test_ft_remains_in_title(self):
        self.assert_parsed("Artist – Track ft. Guest.wav", ("Artist", "Track ft. Guest"))

    def test_windows_path_is_reduced_to_filename(self):
        self.assert_parsed(r"C:\\Music\\Artist - Track.MP3", ("Artist", "Track"))

    def test_repeated_spaces_are_collapsed(self):
        self.assert_parsed("  Artist   -   Track   .mp3", ("Artist", "Track"))

    def test_multiple_annotations_are_removed(self):
        self.assert_parsed(
            "Artist - Track (Official Video) [320kbps].mp3",
            ("Artist", "Track"),
        )


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

    def test_upload_accepts_multiple_files_and_fills_empty_metadata(self):
        self.client.login(username="alice", password="pass12345")
        response = self.client.post(
            reverse("music:track_upload"),
            {
                "album": "",
                "title_0": "",
                "artist_0": "",
                "title_1": "Правленое название",
                "artist_1": "",
                "tags_0": "#Synth, #Ночь",
                "audio_files": [
                    SimpleUploadedFile("02. Сцена - Ночь (Official Video).mp3", b"x"),
                    SimpleUploadedFile("Только_Название.ogg", b"y"),
                ],
            },
        )

        self.assertRedirects(response, reverse("music:library"))
        uploaded = list(Track.objects.filter(owner=self.alice).exclude(pk=self.track.pk))
        self.assertEqual(len(uploaded), 2)
        first = Track.objects.get(owner=self.alice, title="Ночь")
        self.assertEqual(first.artist, "Сцена")
        self.assertSetEqual(set(first.tags.values_list("name", flat=True)), {"synth", "ночь"})
        second = Track.objects.get(owner=self.alice, title="Правленое название")
        self.assertEqual(second.artist, "")

    def test_track_tags_are_updated_when_track_is_edited(self):
        self.client.login(username="alice", password="pass12345")
        response = self.client.post(
            reverse("music:track_edit", args=[self.track.pk]),
            {"title": self.track.title, "artist": self.track.artist, "album": "", "tags": "#JAZZ, #Ночь"},
        )

        self.assertRedirects(response, self.track.get_absolute_url())
        self.assertSetEqual(set(self.track.tags.values_list("name", flat=True)), {"jazz", "ночь"})

    def test_track_tags_are_limited_and_owner_checked(self):
        with self.assertRaises(ValidationError):
            services.set_track_tags(self.alice, self.track, [f"tag{index}" for index in range(11)])
        with self.assertRaises(PermissionDenied):
            services.set_track_tags(self.bob, self.track, ["jazz"])

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

    def test_collaborative_playlist_requires_follow_and_waits_for_acceptance(self):
        with self.assertRaises(PermissionDenied):
            services.create_collaborative_playlist(self.alice, title="Вместе", invitees=[self.bob])

        Follow.objects.create(follower=self.alice, following=self.bob)
        playlist = services.create_collaborative_playlist(self.alice, title="Вместе", invitees=[self.bob])
        services.add_collaborative_playlist_track(self.alice, playlist, self.track)

        self.assertEqual(list(playlist.memberships.values_list("user_id", flat=True)), [self.alice.pk])
        self.assertEqual(services.get_collaborative_playlist_tracks(self.alice, playlist), [self.track])
        with self.assertRaises(PermissionDenied):
            services.get_collaborative_playlist_tracks(self.bob, playlist)

        invite = playlist.invites.get(user=self.bob)
        services.respond_collaborative_invite(self.bob, invite, accept=True)
        self.assertTrue(playlist.memberships.filter(user=self.bob).exists())
        self.assertEqual(services.get_collaborative_playlist_tracks(self.bob, playlist), [self.track])

    def test_collaborative_playlist_form_renders_full_width_invite_selector(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.client.force_login(self.alice)

        response = self.client.get(reverse("music:collaborative_playlist_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="music-form collaborative-playlist-form"')
        self.assertContains(response, 'name="invitees"')
        self.assertContains(response, "multiple")
        self.assertContains(response, "bob")

    def test_collaborative_playlist_members_add_and_remove_tracks(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        playlist = services.create_collaborative_playlist(self.alice, title="Вместе", invitees=[self.bob])
        invite = playlist.invites.get(user=self.bob)
        services.respond_collaborative_invite(self.bob, invite, accept=True)

        second = self._track(self.bob, "Bob 2")
        self.assertTrue(services.add_collaborative_playlist_track(self.bob, playlist, self.track))
        self.assertTrue(services.add_collaborative_playlist_track(self.alice, playlist, second))
        self.assertFalse(services.add_collaborative_playlist_track(self.bob, playlist, self.track))

        tracks = services.get_collaborative_playlist_tracks(self.alice, playlist)
        self.assertEqual([track.pk for track in tracks], [self.track.pk, second.pk])
        self.assertEqual([track.brought_by.pk for track in tracks], [self.bob.pk, self.alice.pk])

        self.assertTrue(services.remove_collaborative_playlist_track(self.alice, playlist, self.track))
        self.assertFalse(services.remove_collaborative_playlist_track(self.bob, playlist, self.track))
        self.assertEqual(services.get_collaborative_playlist_tracks(self.bob, playlist), [second])

    def test_collaborative_playlist_member_can_edit_from_detail_page(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        playlist = services.create_collaborative_playlist(self.alice, title="Вместе", invitees=[self.bob])
        services.respond_collaborative_invite(
            self.bob,
            playlist.invites.get(user=self.bob),
            accept=True,
        )
        self.client.force_login(self.bob)
        details_url = reverse("music:collaborative_playlist_detail", args=[playlist.pk])
        details = self.client.get(details_url)
        self.assertContains(details, "Добавить трек")
        self.assertContains(details, f'data-playlist-track-list="shared-{playlist.pk}"')

        response = self.client.post(
            details_url,
            {"track": self.track.pk},
        )

        self.assertRedirects(response, details_url)
        self.assertEqual(services.get_collaborative_playlist_tracks(self.alice, playlist), [self.track])

        removed = self.client.post(
            reverse(
                "music:collaborative_playlist_remove_track",
                args=[playlist.pk, self.track.pk],
            )
        )
        self.assertRedirects(removed, details_url)
        self.assertEqual(services.get_collaborative_playlist_tracks(self.alice, playlist), [])

    def test_collaborative_playlist_is_private_and_only_creator_can_delete(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        playlist = services.create_collaborative_playlist(self.alice, title="Вместе", invitees=[self.bob])
        with self.assertRaises(PermissionDenied):
            services.get_collaborative_playlist_tracks(self.bob, playlist)
        with self.assertRaises(PermissionDenied):
            services.delete_collaborative_playlist(self.bob, playlist)
        self.client.login(username="bob", password="pass12345")
        self.assertEqual(self.client.get(reverse("music:collaborative_playlist_detail", args=[playlist.pk])).status_code, 404)

    def test_recommendations_prioritize_liked_artists_and_exclude_own_and_liked(self):
        self.track.artist = "Любимая группа"
        self.track.save(update_fields=("artist",))
        favorite_artist_track = self._track(self.bob, "Похожий исполнитель")
        favorite_artist_track.artist = "Любимая группа"
        favorite_artist_track.save(update_fields=("artist",))
        popular_track = self._track(self.bob, "Популярный трек")
        Like.objects.create(user=self.alice, track=self.track)
        Like.objects.create(user=self.bob, track=popular_track)

        recommendations = services.get_recommendations(self.alice, limit=20)

        recommended_ids = [track.pk for track in recommendations]
        self.assertEqual(recommended_ids[0], favorite_artist_track.pk)
        self.assertNotIn(self.track.pk, recommended_ids)
        self.assertNotIn(self.alice.tracks.first().pk, recommended_ids)
        self.assertEqual(len(recommended_ids), len(set(recommended_ids)))
        self.assertNotIn(popular_track.pk, recommended_ids)
        self.assertEqual(recommendations[0].recommendation_reason, "Тот же исполнитель: Любимая группа")

    def test_tag_match_ranks_above_artist_match_and_fewer_likes_rank_first(self):
        services.set_track_tags(self.alice, self.track, ["#Электро"])
        Like.objects.create(user=self.alice, track=self.track)
        tag_match = self._track(self.bob, "По тегу")
        services.set_track_tags(self.bob, tag_match, ["электро"])
        artist_owner = get_user_model().objects.create_user(username="artist-owner")
        artist_match = self._track(artist_owner, "По исполнителю")
        artist_match.artist = self.track.artist
        artist_match.save(update_fields=("artist",))
        popular_tag_match = self._track(self.bob, "Популярный по тегу")
        services.set_track_tags(self.bob, popular_tag_match, ["электро"])
        liker = get_user_model().objects.create_user(username="liker")
        Like.objects.create(user=liker, track=popular_tag_match)

        recommendations = services.get_recommendations(self.alice, limit=10)

        self.assertEqual(recommendations[0], tag_match)
        self.assertEqual(recommendations[1], popular_tag_match)
        self.assertEqual(recommendations[0].recommendation_reason, "Совпадает: электро")
        self.assertEqual(recommendations[2].recommendation_reason, f"Тот же исполнитель: {self.track.artist}")

    def test_recommendations_fallback_to_low_like_tracks_without_history(self):
        low_likes = self._track(self.bob, "Редкий")
        high_likes = self._track(self.bob, "Популярный")
        Like.objects.create(user=self.bob, track=high_likes)

        recommendations = services.get_recommendations(self.alice, limit=10)

        self.assertEqual(recommendations[0], low_likes)
        self.assertEqual(recommendations[0].recommendation_reason, "Новая загрузка")

    def test_recommendations_use_playlists_when_user_has_no_likes(self):
        self.track.artist = "Любимый исполнитель"
        self.track.save(update_fields=("artist",))
        playlist = self._playlist(self.alice)
        services.add_track_to_playlist(self.alice, playlist, self.track)
        candidate = self._track(self.bob, "Из похожего плейлиста")
        candidate.artist = self.track.artist
        candidate.save(update_fields=("artist",))

        recommendations = services.get_recommendations(self.alice, limit=10)

        self.assertIn(candidate, recommendations)

    def test_recommendations_limit_authors_and_consecutive_runs(self):
        services.set_track_tags(self.alice, self.track, ["техно"])
        Like.objects.create(user=self.alice, track=self.track)
        for index in range(5):
            track = self._track(self.bob, f"Bob {index}")
            services.set_track_tags(self.bob, track, ["техно"])
        for index in range(5):
            track = self._track(self.alice, f"Alice {index}")
            track.owner = self.bob
            track.save(update_fields=("owner",))
            services.set_track_tags(self.bob, track, ["техно"])
        other = get_user_model().objects.create_user(username="other")
        for index in range(4):
            track = self._track(other, f"Other {index}")
            services.set_track_tags(other, track, ["техно"])

        recommendations = services.get_recommendations(self.alice, limit=20)

        owner_ids = [track.owner_id for track in recommendations]
        self.assertLessEqual(max(owner_ids.count(owner_id) for owner_id in set(owner_ids)), 3)
        for index in range(2, len(owner_ids)):
            self.assertFalse(owner_ids[index] == owner_ids[index - 1] == owner_ids[index - 2])

    def test_tag_normalization_and_limit(self):
        self.assertEqual(
            services.normalize_tag_names(" #JAZZ, jazz, #Ночь "),
            ["jazz", "ночь"],
        )
        with self.assertRaises(ValidationError):
            services.normalize_tag_names("x")
        with self.assertRaises(ValidationError):
            services.normalize_tag_names("a" * 31)
        with self.assertRaises(ValidationError):
            services.normalize_tag_names([f"tag{i:02}" for i in range(11)])

    def test_track_tag_page_and_radio_api(self):
        services.set_track_tags(self.alice, self.track, ["#Дорога"])
        tag = self.track.tags.get()
        endpoint = reverse("music:radio_tracks_api")
        anonymous_response = self.client.get(endpoint, {"tag": tag.slug})
        self.assertEqual(anonymous_response.status_code, 302)

        self.client.login(username="alice", password="pass12345")
        page = self.client.get(tag.get_absolute_url())
        self.assertContains(page, "#дорога")
        radio_page = self.client.get(reverse("music:radio", args=[tag.slug]))
        self.assertContains(radio_page, "Слушать радио")

        for index in range(11):
            track = self._track(self.bob, f"Radio {index}")
            services.set_track_tags(self.bob, track, ["дорога"])
        first_batch = self.client.get(endpoint, {"tag": tag.slug}).json()["tracks"]
        second_batch = self.client.get(endpoint, {"tag": tag.slug}).json()["tracks"]
        first_ids = {track["id"] for track in first_batch}
        second_ids = {track["id"] for track in second_batch}
        self.assertEqual(len(first_batch), 10)
        self.assertEqual(len(second_batch), 2)
        self.assertFalse(first_ids.intersection(second_ids))

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

    def test_join_session_rejects_self_and_offline_hosts(self):
        with self.assertRaises(ValidationError):
            services.join_session(self.alice, self.alice)
        with self.assertRaises(PermissionDenied):
            services.join_session(self.bob, self.alice)

    def test_join_session_checks_follower_setting_and_can_leave(self):
        NowPlaying.objects.create(user=self.alice, track=self.track, is_playing=True)
        preferences = MusicSettings.objects.create(
            user=self.alice,
            allow_join=MusicSettings.JOIN_FOLLOWERS,
        )
        self.assertFalse(services.can_join_session(self.bob, self.alice))

        Follow.objects.create(follower=self.bob, following=self.alice)
        self.assertTrue(services.can_join_session(self.bob, self.alice))
        session = services.join_session(self.bob, self.alice)
        self.assertEqual(session.host, self.alice)
        NowPlaying.objects.create(user=self.bob, track=self.track, is_playing=True)
        self.assertEqual(services.active_listener_count(self.alice), 1)
        services.leave_session(self.bob)
        self.assertEqual(services.active_listener_count(self.alice), 0)
        self.assertFalse(ListenAlong.objects.filter(listener=self.bob).exists())

        preferences.allow_join = MusicSettings.JOIN_NOBODY
        preferences.save(update_fields=("allow_join",))
        self.assertFalse(services.can_join_session(self.bob, self.alice))

    def test_join_session_requires_fresh_playing_host_state(self):
        state = NowPlaying.objects.create(user=self.alice, track=self.track, is_playing=True)
        NowPlaying.objects.filter(pk=state.pk).update(
            updated_at=timezone.now() - timedelta(seconds=16)
        )
        self.assertFalse(services.can_join_session(self.bob, self.alice))

    def test_join_session_is_available_while_host_is_paused(self):
        NowPlaying.objects.create(
            user=self.alice,
            track=self.track,
            position_seconds=12,
            duration_seconds=90,
            is_playing=False,
        )

        self.assertTrue(services.can_join_session(self.bob, self.alice))
        session = services.join_session(self.bob, self.alice)
        self.assertEqual(session.host, self.alice)

    def test_join_and_leave_api(self):
        NowPlaying.objects.create(user=self.alice, track=self.track, is_playing=True)
        self.client.login(username="bob", password="pass12345")

        joined = self.client.post(
            reverse("music:listen_along_join", args=[self.alice.username]),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.json()["host"], self.alice.username)
        self.assertTrue(ListenAlong.objects.filter(listener=self.bob, host=self.alice).exists())

        left = self.client.post(reverse("music:listen_along_leave"), HTTP_ACCEPT="application/json")
        self.assertEqual(left.status_code, 200)
        self.assertFalse(ListenAlong.objects.filter(listener=self.bob).exists())

    def test_now_playing_template_tag_renders_card(self):
        NowPlaying.objects.create(
            user=self.alice,
            track=self.track,
            position_seconds=35,
            duration_seconds=180,
            is_playing=False,
        )
        rendered = Template(
            "{% load music_tags %}{% now_playing_card profile_user %}"
        ).render(Context({"profile_user": self.alice, "user": self.bob}))

        self.assertIn("На паузе", rendered)
        self.assertIn("Слушать вместе", rendered)
        self.assertIn("00:35", rendered)
        self.assertIn('aria-valuenow="19"', rendered)

    def test_other_users_profile_always_offers_listen_along_for_fresh_paused_track(self):
        NowPlaying.objects.create(
            user=self.alice,
            track=self.track,
            position_seconds=12,
            duration_seconds=90,
            is_playing=False,
        )
        self.client.force_login(self.bob)

        response = self.client.get(reverse("accounts:profile", args=[self.alice.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Слушать вместе")
        self.assertContains(response, "Синхронно с @alice")
        self.assertContains(response, 'data-host-is-playing="false"')
        self.assertContains(response, f'data-track-id="{self.track.pk}"')

    def test_other_users_profile_shows_listen_along_when_they_are_offline(self):
        self.client.force_login(self.bob)

        response = self.client.get(reverse("accounts:profile", args=[self.alice.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Слушать вместе")
        self.assertContains(response, "Нет активного трека")
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
