from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.feed.models import Post
from apps.music.models import Track


class Command(BaseCommand):
    help = "Создаёт пользователей, посты и треки для демонстрации."

    def handle(self, *args, **options):
        User = get_user_model()
        users = []
        for username in ("demo_alice", "demo_bob", "demo_carol"):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com"},
            )
            if created:
                user.set_password("demo-password")
                user.save(update_fields=["password"])
            users.append(user)

        for user, text in (
            (users[0], "Первый демонстрационный пост."),
            (users[1], "Пост для проверки комментариев."),
        ):
            Post.objects.get_or_create(author=user, text=text)

        for artist, title in (("Demo Artist", "Welcome"), ("Demo Artist", "Another Day")):
            Track.objects.get_or_create(artist=artist, title=title)

        self.stdout.write(self.style.SUCCESS("Демо-данные готовы. Пароль пользователей: demo-password"))
