from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from feed.models import Post

from .models import Comment
from .services import add_comment, delete_comment


class CommentServicesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user("author", password="pass")
        self.other = User.objects.create_user("other", password="pass")
        self.post = Post.objects.create(author=self.author, text="post")
        self.comment = add_comment(post=self.post, author=self.other, text="comment")

    def test_empty_comment_is_rejected(self):
        with self.assertRaises(ValidationError):
            add_comment(post=self.post, author=self.other, text=" ")

    def test_comment_author_and_post_author_can_delete(self):
        delete_comment(comment=self.comment, user=self.author)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        comment = add_comment(post=self.post, author=self.other, text="again")
        delete_comment(comment=comment, user=self.other)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_unrelated_user_cannot_delete(self):
        outsider = get_user_model().objects.create_user("outsider", password="pass")
        with self.assertRaises(PermissionDenied):
            delete_comment(comment=self.comment, user=outsider)
