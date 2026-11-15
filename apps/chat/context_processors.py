from .services import unread_count


def chat_notifications(request):
    if not request.user.is_authenticated:
        return {"chat_unread_count": 0}
    return {"chat_unread_count": unread_count(request.user)}
