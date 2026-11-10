from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image


User = get_user_model()


def png_upload(name="avatar.png"):
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="blue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class UserModelTests(TestCase):
    def test_bio_is_limited_to_300_characters(self):
        user = User(username="long-bio", bio="x" * 301)
        user.set_password("Strong-password-9021")

        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_profile_avatar_accepts_png(self):
        user = User(username="with-avatar", avatar=png_upload())
        user.set_password("Strong-password-9021")

        user.full_clean()

    def test_profile_avatar_rejects_unsupported_extension(self):
        user = User(username="wrong-avatar", avatar=png_upload("avatar.gif"))
        user.set_password("Strong-password-9021")

        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_profile_avatar_rejects_files_over_5_mb(self):
        oversized_file = SimpleUploadedFile(
            "avatar.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        user = User(username="oversized-avatar", avatar=oversized_file)
        user.set_password("Strong-password-9021")

        with self.assertRaises(ValidationError):
            user.full_clean()


class AccountViewTests(TestCase):
    def test_registration_creates_user_and_signs_them_in(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new-user",
                "email": "new@example.com",
                "password1": "Strong-password-9021",
                "password2": "Strong-password-9021",
            },
        )

        user = User.objects.get(username="new-user")
        self.assertRedirects(
            response,
            reverse("accounts:profile", kwargs={"username": user.username}),
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_profile_can_be_viewed_without_authentication(self):
        user = User.objects.create_user(username="public-profile")

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": user.username})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, user.username)

    def test_login_and_logout_use_django_sessions(self):
        password = "Strong-password-9021"
        User.objects.create_user(username="session-user", password=password)

        login_response = self.client.post(
            reverse("accounts:login"),
            {"username": "session-user", "password": password},
        )
        self.assertRedirects(login_response, "/")
        self.assertTrue(self.client.session.get("_auth_user_id"))

        logout_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout_response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_can_update_their_bio_and_avatar(self):
        user = User.objects.create_user(username="profile-owner")
        self.client.force_login(user)

        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                response = self.client.post(
                    reverse(
                        "accounts:profile_edit",
                        kwargs={"username": user.username},
                    ),
                    {"bio": "Hello!", "avatar": png_upload()},
                )

        user.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("accounts:profile", kwargs={"username": user.username}),
        )
        self.assertEqual(user.bio, "Hello!")
        self.assertTrue(user.avatar.name.startswith("avatars/"))

    def test_user_cannot_edit_another_profile(self):
        owner = User.objects.create_user(username="owner")
        other_user = User.objects.create_user(username="other")
        self.client.force_login(other_user)

        response = self.client.get(
            reverse("accounts:profile_edit", kwargs={"username": owner.username})
        )

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login_before_editing(self):
        response = self.client.get(
            reverse("accounts:profile_edit", kwargs={"username": "someone"})
        )

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next=/u/someone/edit/",
        )
