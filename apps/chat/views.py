from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ConversationForm, MessageForm
from .models import Conversation, Message
from .services import (
    create_conversation,
    delete_message,
    get_or_create_dialog,
    mark_read,
    send_message,
    unread_count,
)

User = get_user_model()


@login_required
def inbox(request):
    conversations = (
        request.user.conversations.prefetch_related("participants", "messages")
        .order_by("-created_at")
    )
    return render(
        request,
        "chat/inbox.html",
        {
            "conversations": conversations,
            "unread_total": unread_count(request.user),
            "conversation_form": ConversationForm(),
        },
    )


@login_required
def create(request):
    if request.method != "POST":
        return redirect("chat:inbox")
    form = ConversationForm(request.POST)
    if form.is_valid():
        usernames = {
            value.strip()
            for value in form.cleaned_data["usernames"].split(",")
            if value.strip()
        }
        users = list(User.objects.filter(username__in=usernames))
        if len(users) != len(usernames):
            form.add_error("usernames", "Один или несколько пользователей не найдены.")
        else:
            conversation = create_conversation(
                creator=request.user,
                kind=form.cleaned_data["kind"],
                title=form.cleaned_data["title"],
                participants=users,
            )
            return redirect("chat:dialog", conversation_id=conversation.pk)
    conversations = request.user.conversations.prefetch_related("participants", "messages")
    return render(
        request,
        "chat/inbox.html",
        {
            "conversations": conversations,
            "unread_total": unread_count(request.user),
            "conversation_form": form,
        },
    )


@login_required
def dialog_with_user(request, username):
    other_user = get_object_or_404(User, username=username)
    try:
        conversation, _ = get_or_create_dialog(request.user, other_user)
    except ValidationError:
        raise PermissionDenied("Нельзя начать диалог с самим собой.")
    return redirect("chat:dialog", conversation_id=conversation.pk)


@login_required
def dialog(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.filter(participants=request.user).prefetch_related("messages__attachments"),
        pk=conversation_id,
    )
    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                send_message(conversation, request.user, form.cleaned_data["text"], form.cleaned_data["file"])
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect("chat:dialog", conversation_id=conversation.pk)
    else:
        form = MessageForm()
    mark_read(conversation, request.user)
    return render(request, "chat/dialog.html", {"conversation": conversation, "form": form, "user": request.user})


@login_required
def delete(request, message_id):
    if request.method != "POST":
        return redirect("chat:inbox")
    message = get_object_or_404(Message, pk=message_id)
    conversation_id = message.conversation_id
    delete_message(message, request.user)
    return redirect("chat:dialog", conversation_id=conversation_id)
