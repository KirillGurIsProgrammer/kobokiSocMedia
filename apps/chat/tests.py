from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Conversation
from .services import get_or_create_dialog, mark_read, send_message, unread_count


class ChatServicesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="pass")
        self.bob = User.objects.create_user("bob", password="pass")
        self.eve = User.objects.create_user("eve", password="pass")
        self.dialog, _ = get_or_create_dialog(self.alice, self.bob)

    def test_dialog_is_unique_for_a_pair(self):
        same_dialog, created = get_or_create_dialog(self.bob, self.alice)
        self.assertFalse(created)
        self.assertEqual(self.dialog.pk, same_dialog.pk)

    def test_self_dialog_is_rejected(self):
        with self.assertRaises(ValidationError):
            get_or_create_dialog(self.alice, self.alice)

    def test_non_participant_cannot_send(self):
        with self.assertRaises(PermissionDenied):
            send_message(self.dialog, self.eve, "secret")

    def test_unread_count_and_mark_read(self):
        send_message(self.dialog, self.alice, "hello")
        self.assertEqual(unread_count(self.bob), 1)
        mark_read(self.dialog, self.bob)
        self.assertEqual(unread_count(self.bob), 0)

    def test_text_or_attachment_is_required(self):
        with self.assertRaises(ValidationError):
            send_message(self.dialog, self.alice)
        message = send_message(
            self.dialog,
            self.alice,
            file=SimpleUploadedFile("note.pdf", b"no"),
        )
        self.assertEqual(message.text, "")


class ChatViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="pass")
        self.bob = User.objects.create_user("bob", password="pass")
        self.dialog, _ = get_or_create_dialog(self.alice, self.bob)

    def test_other_user_gets_404_for_dialog(self):
        self.client.force_login(self.alice)
        other = get_user_model().objects.create_user("eve", password="pass")
        response = self.client.get(reverse("chat:dialog", args=[self.dialog.pk]))
        self.assertEqual(response.status_code, 200)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("chat:dialog", args=[self.dialog.pk])).status_code, 404)

    def test_dialog_renders_styled_messages_and_composer(self):
        send_message(self.dialog, self.alice, "Привет, Боб!")
        self.client.force_login(self.alice)

        response = self.client.get(reverse("chat:dialog", args=[self.dialog.pk]))

        self.assertContains(response, "message-card--mine")
        self.assertContains(response, "Привет, Боб!")
        self.assertContains(response, "data-chat-messages")
        self.assertContains(response, "chat-form-actions")
        self.assertContains(response, "Прикрепить файл")
        self.assertContains(response, 'placeholder="Напишите сообщение')

    def test_anonymous_home_page_redirects_to_site_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/accounts/login/?next=/")

    def test_anonymous_user_is_sent_to_site_login(self):
        response = self.client.get(reverse("chat:inbox"))
        self.assertRedirects(response, "/accounts/login/?next=/chat/")

    def test_site_login_page_is_not_admin_login(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Войти в Koboki")
