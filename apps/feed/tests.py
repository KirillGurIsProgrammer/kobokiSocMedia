from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.services import follow

from .models import Post
from .services import create_post, delete_post, get_feed_for, update_post


User = get_user_model()


def png_upload(name="post.png"):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="purple").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class PostModelTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="post-author")

    def test_post_rejects_empty_or_whitespace_text(self):
        for text in ("", "   \n\t"):
            post = Post(author=self.author, text=text)
            with self.subTest(text=repr(text)), self.assertRaises(ValidationError):
                post.full_clean()

    def test_post_rejects_text_over_2000_characters(self):
        post = Post(author=self.author, text="x" * 2001)

        with self.assertRaises(ValidationError):
            post.full_clean()

    def test_post_requires_complete_track_details(self):
        post = Post(
            author=self.author,
            text="Listening now",
            track_title="Dreams",
        )

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

        with self.assertNumQueries(1):
            feed_posts = list(get_feed_for(self.user))

        self.assertCountEqual(
            [post.pk for post in feed_posts],
            [own_post.pk, followed_post.pk, other_post.pk],
        )
        self.assertTrue(
            all("author" in post._state.fields_cache for post in feed_posts)
        )

    def test_create_post_assigns_author_and_saves(self):
        post = create_post(self.user, text="Listening now")

        self.assertEqual(post.author, self.user)
        self.assertEqual(Post.objects.get(pk=post.pk).text, "Listening now")

    def test_create_post_can_attach_a_track(self):
        post = create_post(
            self.user,
            text="On repeat",
            track_title="Dreams",
            track_artist="Fleetwood Mac",
            track_url="https://open.spotify.com/track/example",
        )

        self.assertEqual(post.track_title, "Dreams")
        self.assertEqual(post.track_artist, "Fleetwood Mac")
        self.assertEqual(post.track_url, "https://open.spotify.com/track/example")

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
        post = Post.objects.create(
            author=self.user,
            text="Listening now",
            track_title="Old song",
            track_artist="Old artist",
            track_url="https://example.com/old",
        )

        update_post(
            self.user,
            post,
            text=post.text,
            track_title="New song",
            track_artist="New artist",
            track_url="https://example.com/new",
        )
        self.assertEqual(post.track_title, "New song")

        update_post(
            self.user,
            post,
            text=post.text,
            track_title="",
            track_artist="",
            track_url="",
        )
        self.assertEqual(post.track_title, "")
        self.assertEqual(post.track_url, "")

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

    def test_create_post_view_saves_post_and_redirects(self):
        response = self.client.post(
            reverse("feed:post_create"),
            {"text": "Great album today"},
        )

        self.assertRedirects(response, reverse("feed:feed"))
        self.assertTrue(
            Post.objects.filter(author=self.user, text="Great album today").exists()
        )

    def test_create_post_view_saves_attached_track_and_displays_it(self):
        response = self.client.post(
            reverse("feed:post_create"),
            {
                "text": "Great album today",
                "track_title": "Dreams",
                "track_artist": "Fleetwood Mac",
                "track_url": "https://open.spotify.com/track/example",
            },
        )

        self.assertRedirects(response, reverse("feed:feed"))
        post = Post.objects.get(author=self.user, track_title="Dreams")
        feed_response = self.client.get(reverse("feed:feed"))
        self.assertContains(feed_response, "Fleetwood Mac")
        self.assertContains(feed_response, post.track_url)

    def test_create_post_view_accepts_image(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                response = self.client.post(
                    reverse("feed:post_create"),
                    {"text": "Cover art", "image": png_upload()},
                )

        self.assertRedirects(response, reverse("feed:feed"))
        self.assertTrue(Post.objects.get(author=self.user).image.name.startswith("posts/"))

    def test_post_detail_is_public_and_has_comment_integration_placeholder(self):
        post = Post.objects.create(author=self.followed, text="Track notes")

        self.client.logout()
        response = self.client.get(
            reverse("feed:post_detail", kwargs={"post_id": post.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track notes")
        self.assertContains(response, "Комментарии")

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
