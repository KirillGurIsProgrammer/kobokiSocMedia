from django.core.exceptions import PermissionDenied, ValidationError

from .models import Comment


def add_comment(*, post, author, text):
    text = (text or "").strip()
    if not 1 <= len(text) <= 1000:
        raise ValidationError("Комментарий должен содержать от 1 до 1000 символов.")
    return Comment.objects.create(post=post, author=author, text=text)


def delete_comment(*, comment, user):
    if comment.author_id != user.pk and comment.post.author_id != user.pk:
        raise PermissionDenied("Удалять комментарий может только его автор или автор поста.")
    comment.delete()
