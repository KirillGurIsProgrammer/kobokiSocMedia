from django import forms

from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("text", "image", "track_title", "track_artist", "track_url")
        labels = {
            "text": "Текст публикации",
            "image": "Изображение (необязательно)",
        }
        help_texts = {
            "track_title": "Заполни все три поля, чтобы прикрепить трек.",
            "track_artist": "Имя исполнителя или группы.",
            "track_url": "Ссылка на страницу трека в музыкальном сервисе.",
        }
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Чем хочешь поделиться?",
                }
            ),
            "track_title": forms.TextInput(
                attrs={"placeholder": "Например, Dreams"}
            ),
            "track_artist": forms.TextInput(
                attrs={"placeholder": "Например, Fleetwood Mac"}
            ),
            "track_url": forms.URLInput(
                attrs={
                    "placeholder": "https://open.spotify.com/track/…",
                    "autocomplete": "url",
                }
            ),
        }
