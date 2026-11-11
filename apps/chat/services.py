from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.db import transaction

from .models import Attachment, Conversation, Message

User = get_user_model()


@transaction.atomic
def get_or_create_dialog(user_a, user_b):
    if user_a.pk == user_b.pk:
        raise ValidationError("Нельзя создать диалог с самим собой.")
    conversation = (
        Conversation.objects.filter(participants__in=[user_a, user_b])
        .annotate(participant_count=Count("participants", distinct=True))
        .filter(participant_count=2)
        .first()
    )
    if conversation:
        return conversation, False
    conversation = Conversation.objects.create()
    conversation.participants.add(user_a, user_b)
    return conversation, True


def ensure_participant(conversation, user):
    if not conversation.participants.filter(pk=user.pk).exists():
        raise PermissionDenied("Вы не участник этого диалога.")


@transaction.atomic
def send_message(conversation, sender, text="", file=None):
    ensure_participant(conversation, sender)
    text = (text or "").strip()
    if not text and file is None:
        raise ValidationError("Введите текст или добавьте вложение.")
    if len(text) > 2000:
        raise ValidationError("Текст сообщения не должен превышать 2000 символов.")
    message = Message.objects.create(conversation=conversation, sender=sender, text=text)
    if file is not None:
        attachment = Attachment(message=message, file=file)
        attachment.full_clean()
        attachment.save()
    return message


def mark_read(conversation, user):
    ensure_participant(conversation, user)
    return conversation.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)


def unread_count(user):
    return Message.objects.filter(conversation__participants=user, is_read=False).exclude(sender=user).count()
