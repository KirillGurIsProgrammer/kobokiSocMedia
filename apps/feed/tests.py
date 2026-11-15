from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.services import follow
from apps.music.models import Track

from .forms import PostForm
from .models import Post
from .services import create_post, delete_post, get_feed_for, update_post


User = get_user_model()


def png_upload(name="post.png"):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="purple").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def mp3_upload(name="track.mp3"):
    return SimpleUploadedFile(name, b"ID3-test-audio", content_type="audio/mpeg")


class PostModelTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="post-author")

    def test_post_form_uses_library_track_instead_of_external_music_links(self):
        form = PostForm()

        self.assertIn("track", form.fields)
        self.assertIn("track_file", form.fields)
        self.assertNotIn("track_url", form.fields)
        self.assertIn("data-track-picker", str(form["track"]))

    def test_post_rejects_empty_or_whitespace_text(self):
        for text in ("", "   \n\t"):
            post = Post(author=self.author, text=text)
            with self.subTest(text=repr(text)), self.assertRaises(ValidationError):
                post.full_clean()

    def test_post_rejects_text_over_2000_characters(self):
        post = Post(author=self.author, text="x" * 2001)

        with self.assertRaises(ValidationError):
            post.full_clean()

    def test_post_accepts_a_valid_png_image(self):
        post = Post(author=self.author, text="Now playing", image=png_upload())

        post.full_clean()

    def test_post_rejects_unsupported_image_extension(self):
        post = Post(
            author=self.author,
            text="Now playing",
            image=png_upload("cover.gif"),
        )

        with self.assertRaises(ValidationError):
            post.full_clean()

    def test_post_rejects_images_over_5_mb(self):
        upload = SimpleUploadedFile(
            "cover.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        post = Post(author=self.author, text="Now playing", image=upload)

        with self.assertRaises(ValidationError):
            post.full_clean()


class FeedServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="feed-user")
        self.followed = User.objects.create_user(username="followed-user")
        self.other = User.objects.create_user(username="other-user")

    def test_feed_contains_posts_from_all_users(self):
        own_post = Post.objects.create(author=self.user, text="My post")
        followed_post = Post.objects.create(
            author=self.followed,
            text="Followed post",
        )
        other_post = Post.objects.create(author=self.other, text="Community post")
        follow(self.user, self.followed)

        with self.assertNumQueries(3):
            feed_entries = list(get_feed_for(self.user))

        self.assertCountEqual(
            [entry.item.pk for entry in feed_entries],
            [own_post.pk, followed_post.pk, other_post.pk],
        )
        self.assertTrue(
            all(
                "author" in entry.item._state.fields_cache
                for entry in feed_entries
            )
        )

    def test_create_post_assigns_author_and_saves(self):
        post = create_post(self.user, text="Listening now")

        self.assertEqual(post.author, self.user)
        self.assertEqual(Post.objects.get(pk=post.pk).text, "Listening now")

    def test_delete_post_rejects_non_author(self):
        post = Post.objects.create(author=self.followed, text="Private to author")

        with self.assertRaises(PermissionDenied):
            delete_post(self.user, post)

        self.assertTrue(Post.objects.filter(pk=post.pk).exists())

    def test_update_post_changes_text_for_author(self):
        post = Post.objects.create(author=self.user, text="Old text")

        updated_post = update_post(self.user, post, text="Updated text")

        self.assertEqual(updated_post.text, "Updated text")
        self.assertEqual(Post.objects.get(pk=post.pk).text, "Updated text")

    def test_update_post_can_replace_or_remove_track(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                track = Track.objects.create(
                    owner=self.user,
                    title="Old song",
                    artist="Old artist",
                    audio_file=mp3_upload(),
                )
                post = Post.objects.create(
                    author=self.user, text="Listening now", track=track
                )
                new_track = Track.objects.create(
                    owner=self.followed,
                    title="New song",
                    artist="New artist",
                    audio_file=mp3_upload("new-track.mp3"),
                )

                update_post(
                    self.user,
                    post,
                    text=post.text,
                    track=new_track,
                )
                self.assertEqual(post.track, new_track)

                update_post(self.user, post, text=post.text, track=None)
        self.assertIsNone(post.track)

    def test_uploaded_mp3_is_added_to_library_and_attached_to_post(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                post = create_post(
                    self.user,
                    text="On repeat",
                    track_file=mp3_upload(),
                    track_title="Dreams",
                    track_artist="Fleetwood Mac",
                )

        self.assertEqual(post.track.title, "Dreams")
        self.assertEqual(post.track.artist, "Fleetwood Mac")
        self.assertEqual(post.track.owner, self.user)

    def test_update_post_rejects_non_author(self):
        post = Post.objects.create(author=self.followed, text="Original text")

        with self.assertRaises(PermissionDenied):
            update_post(self.user, post, text="Changed by another user")

        self.assertEqual(Post.objects.get(pk=post.pk).text, "Original text")


class FeedViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="viewer")
        self.followed = User.objects.create_user(username="creator")
        self.client.force_login(self.user)

    def test_feed_is_limited_to_ten_posts_per_page(self):
        for index in range(11):
            Post.objects.create(author=self.followed, text=f"Post {index}")

        first_page = self.client.get(reverse("feed:feed"))
        second_page = self.client.get(reverse("feed:feed"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["page_obj"].object_list), 10)
        self.assertTrue(first_page.context["page_obj"].has_next())
        self.assertEqual(len(second_page.context["page_obj"].object_list), 1)

    def test_feed_displays_posts_from_users_the_viewer_does_not_follow(self):
        Post.objects.create(author=self.followed, text="Community post")

        response = self.client.get(reverse("feed:feed"))

        self.assertContains(response, "Community post")

    def test_music_upload_is_published_as_a_playable_feed_card(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                upload_response = self.client.post(
                    reverse("music:track_upload"),
                    {
                        "title": "New song",
                        "artist": "New artist",
                        "audio_file": mp3_upload(),
                    },
                )
                feed_response = self.client.get(reverse("feed:feed"))

        self.assertEqual(upload_response.status_code, 302)
        self.assertContains(feed_response, "New song")
        self.assertContains(feed_response, "New artist")
        self.assertContains(feed_response, "data-track-play")
        self.assertContains(feed_response, "tracks/track.mp3")

    def test_feed_link_is_highlighted_on_feed_and_music_link_on_music_pages(self):
        feed_response = self.client.get(reverse("feed:feed"))
        music_response = self.client.get(reverse("music:library"))

        self.assertContains(
            feed_response, 'class="side-link is-active" href="/"'
        )
        self.assertContains(
            music_response, 'class="side-link is-active" href="/music/"'
        )

    def test_create_post_view_saves_post_and_redirects(self):
        response = self.client.post(
            reverse("feed:post_create"),
            {"text": "Great album today"},
        )

        self.assertRedirects(response, reverse("feed:feed"))
        self.assertTrue(
            Post.objects.filter(author=self.user, text="Great album today").exists()
        )

    def test_create_post_view_attaches_a_library_track_and_renders_player(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                track = Track.objects.create(
                    owner=self.followed,
                    title="Dreams",
                    artist="Fleetwood Mac",
                    audio_file=mp3_upload(),
                )
                response = self.client.post(
                    reverse("feed:post_create"),
                    {"text": "Great album today", "track": track.pk},
                )
                feed_response = self.client.get(reverse("feed:feed"))

        self.assertRedirects(response, reverse("feed:feed"))
        post = Post.objects.get(author=self.user, track=track)
        self.assertEqual(post.track, track)
        self.assertContains(feed_response, "Fleetwood Mac")
        self.assertContains(feed_response, "data-track-play")
        self.assertContains(feed_response, track.audio_file.url)

    def test_create_post_view_uploads_mp3_into_library(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                response = self.client.post(
                    reverse("feed:post_create"),
                    {
                        "text": "Great album today",
                        "track_file": mp3_upload(),
                        "track_title": "Dreams",
                        "track_artist": "Fleetwood Mac",
                    },
                )

        self.assertRedirects(response, reverse("feed:feed"))
        post = Post.objects.get(author=self.user)
        self.assertEqual(post.track.title, "Dreams")
        self.assertEqual(post.track.owner, self.user)
        self.assertTrue(post.track.audio_file.name.startswith("tracks/"))

    def test_create_post_rejects_non_mp3_audio_upload(self):
        response = self.client.post(
            reverse("feed:post_create"),
            {
                "text": "Great album today",
                "track_file": SimpleUploadedFile(
                    "track.wav", b"wav", content_type="audio/wav"
                ),
                "track_title": "Dreams",
                "track_artist": "Fleetwood Mac",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(author=self.user).exists())
        self.assertContains(response, "Можно прикрепить только MP3-файл.")

    def test_create_post_view_accepts_image(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                response = self.client.post(
                    reverse("feed:post_create"),
                    {"text": "Cover art", "image": png_upload()},
                )

        self.assertRedirects(response, reverse("feed:feed"))
        self.assertTrue(Post.objects.get(author=self.user).image.name.startswith("posts/"))

    def test_post_detail_is_public_and_displays_comments(self):
        post = Post.objects.create(author=self.followed, text="Track notes")

        self.client.logout()
        response = self.client.get(
            reverse("feed:post_detail", kwargs={"post_id": post.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track notes")
        self.assertContains(response, "Комментарии")
        self.assertNotContains(response, "будет подключён")

    def test_post_can_be_liked_and_unliked(self):
        post = Post.objects.create(author=self.followed, text="Creator post")
        url = reverse("feed:post_toggle_like", args=[post.pk])

        liked_response = self.client.post(
            url,
            {"next": reverse("feed:feed")},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(liked_response.status_code, 200)
        self.assertEqual(liked_response.json(), {"liked": True, "like_count": 1})
        self.assertTrue(post.likes.filter(user=self.user).exists())
        self.assertContains(self.client.get(reverse("feed:feed")), "Нравится")

        unliked_response = self.client.post(
            url,
            {"next": reverse("feed:feed")},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(unliked_response.json(), {"liked": False, "like_count": 0})
        self.assertFalse(post.likes.filter(user=self.user).exists())

    def test_post_like_requires_login(self):
        post = Post.objects.create(author=self.followed, text="Creator post")
        self.client.logout()

        response = self.client.post(
            reverse("feed:post_toggle_like", args=[post.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(post.likes.exists())

    def test_comment_can_be_added_from_feed_without_leaving_it(self):
        post = Post.objects.create(author=self.followed, text="Creator post")

        response = self.client.post(
            reverse("comments:add", args=[post.pk]),
            {"text": "Great post", "next": reverse("feed:feed")},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["text"], "Great post")
        self.assertEqual(response.json()["comment_count"], 1)
        self.assertTrue(post.comments.filter(author=self.user, text="Great post").exists())
        self.assertContains(self.client.get(reverse("feed:feed")), "Great post")

    def test_comment_fallback_redirects_back_to_post_anchor(self):
        post = Post.objects.create(author=self.followed, text="Creator post")
        feed_url = reverse("feed:feed")

        response = self.client.post(
            reverse("comments:add", args=[post.pk]),
            {"text": "Great post", "next": f"{feed_url}#post-{post.pk}"},
        )

        self.assertRedirects(response, f"{feed_url}#post-{post.pk}")
        self.assertTrue(post.comments.filter(author=self.user, text="Great post").exists())

    def test_only_author_can_delete_post(self):
        post = Post.objects.create(author=self.followed, text="Creator post")

        response = self.client.post(
            reverse("feed:post_delete", kwargs={"post_id": post.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())

    def test_only_author_can_edit_post(self):
        post = Post.objects.create(author=self.followed, text="Creator post")

        response = self.client.get(
            reverse("feed:post_edit", kwargs={"post_id": post.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_author_can_edit_own_post(self):
        post = Post.objects.create(author=self.user, text="Original text")

        response = self.client.post(
            reverse("feed:post_edit", kwargs={"post_id": post.pk}),
            {"text": "Updated text"},
        )

        self.assertRedirects(
            response,
            reverse("feed:post_detail", kwargs={"post_id": post.pk}),
        )
        post.refresh_from_db()
        self.assertEqual(post.text, "Updated text")

    def test_author_can_delete_own_post_with_post_request(self):
        post = Post.objects.create(author=self.user, text="My post")

        response = self.client.post(
            reverse("feed:post_delete", kwargs={"post_id": post.pk})
        )

        self.assertRedirects(response, reverse("feed:feed"))
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_delete_route_rejects_get(self):
        post = Post.objects.create(author=self.user, text="My post")

        response = self.client.get(
            reverse("feed:post_delete", kwargs={"post_id": post.pk})
        )

        self.assertEqual(response.status_code, 405)

    def test_anonymous_user_is_redirected_to_login_for_feed(self):
        self.client.logout()

        response = self.client.get(reverse("feed:feed"))

        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/")
