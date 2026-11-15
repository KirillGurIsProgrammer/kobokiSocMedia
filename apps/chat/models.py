from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.validators import validate_attachment


class Conversation(models.Model):
    DIRECT = "direct"
    GROUP = "group"
    CHANNEL = "channel"
    KIND_CHOICES = (
        (DIRECT, "Диалог"),
        (GROUP, "Группа"),
        (CHANNEL, "Канал"),
    )
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="conversations")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=DIRECT)
    title = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.pk and self.kind == self.DIRECT and self.participants.count() != 2:
            raise ValidationError("Диалог должен содержать ровно двух участников.")
        if self.kind != self.DIRECT and not self.title.strip():
            raise ValidationError("У группы или канала должно быть название.")

    def __str__(self):
        return self.title or f"Conversation #{self.pk}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        if not self.text.strip() and not self.attachments.exists():
            raise ValidationError("Сообщение должно содержать текст или вложение.")


class Attachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="chat/%Y/%m/%d/", validators=[validate_attachment])
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_image(self):
        return self.file.name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
