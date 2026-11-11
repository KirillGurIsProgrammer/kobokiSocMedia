from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.validators import validate_attachment


class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.pk and self.participants.count() != 2:
            raise ValidationError("Диалог должен содержать ровно двух участников.")

    def __str__(self):
        return f"Conversation #{self.pk}"


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
