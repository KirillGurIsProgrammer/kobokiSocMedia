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
        Conversation.objects.filter(kind=Conversation.DIRECT, participants__in=[user_a, user_b])
        .annotate(participant_count=Count("participants", distinct=True))
        .filter(participant_count=2)
        .first()
    )
    if conversation:
        return conversation, False
    conversation = Conversation.objects.create(kind=Conversation.DIRECT, created_by=user_a)
    conversation.participants.add(user_a, user_b)
    return conversation, True


@transaction.atomic
def create_conversation(*, creator, kind, title, participants=()):
    if kind not in {Conversation.GROUP, Conversation.CHANNEL}:
        raise ValidationError("Неизвестный тип чата.")
    title = (title or "").strip()
    if not title:
        raise ValidationError("Укажите название чата.")
    users = {creator, *participants}
    conversation = Conversation.objects.create(kind=kind, title=title, created_by=creator)
    conversation.participants.add(*users)
    return conversation


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


@transaction.atomic
def delete_message(message, user):
    ensure_participant(message.conversation, user)
    if message.sender_id != user.pk:
        raise PermissionDenied("Удалять можно только свои сообщения.")
    message.delete()
