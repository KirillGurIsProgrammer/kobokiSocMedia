from django import forms
from django.core.exceptions import ValidationError

from apps.core.validators import validate_audio
from apps.music.models import Track

from .models import Post


def validate_mp3(upload):
    if not upload.name.lower().endswith(".mp3"):
        raise ValidationError("Можно прикрепить только MP3-файл.")
    validate_audio(upload)


class PostForm(forms.ModelForm):
    track_file = forms.FileField(
        label="Загрузить MP3",
        required=False,
        validators=[validate_mp3],
        help_text=(
            "Файл будет добавлен в вашу музыкальную библиотеку (до 20 МБ) "
            "и заменит выбранный трек."
        ),
    )
    track_title = forms.CharField(
        label="Название загружаемого трека",
        max_length=100,
        required=False,
    )
    track_artist = forms.CharField(
        label="Исполнитель загружаемого трека",
        max_length=100,
        required=False,
    )

    class Meta:
        model = Post
        fields = ("text", "image", "track")
        labels = {
            "text": "Текст публикации",
            "image": "Изображение (необязательно)",
            "track": "Выбрать песню из библиотеки",
        }
        help_texts = {
            "track": "Можно выбрать уже загруженный трек или добавить MP3 ниже.",
        }
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Чем хочешь поделиться?",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["track"].queryset = Track.objects.select_related(
            "owner", "album"
        ).order_by("title", "artist", "pk")
        self.fields["track"].empty_label = "Без трека"

    def clean(self):
        cleaned_data = super().clean()
        track = cleaned_data.get("track")
        track_file = cleaned_data.get("track_file")
        track_title = cleaned_data.get("track_title", "").strip()
        track_artist = cleaned_data.get("track_artist", "").strip()

        if track_file:
            cleaned_data["track"] = None
        if track_file and not track_title:
            self.add_error("track_title", "Укажите название загружаемого трека.")
        if track_file and not track_artist:
            self.add_error("track_artist", "Укажите исполнителя загружаемого трека.")
        if not track_file and (track_title or track_artist):
            self.add_error(
                "track_file",
                "Чтобы указать данные нового трека, загрузите MP3-файл.",
            )
        return cleaned_data
