from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.core.validators import validate_audio, validate_image
from . import services
from .models import Album, MusicSettings, Playlist, Track
from apps.accounts.models import Follow

User = get_user_model()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            if not data:
                return super().clean(None, initial)
            return [super(MultipleFileField, self).clean(item, initial) for item in data]
        return [super().clean(data, initial)]


class TrackUploadForm(forms.Form):
    audio_files = MultipleFileField(
        label="Аудиофайлы",
        widget=MultipleFileInput(attrs={"accept": ".mp3,.wav,.ogg", "multiple": True}),
    )
    album = forms.ModelChoiceField(
        label="Альбом",
        queryset=Album.objects.none(),
        required=False,
        empty_label="Без альбома",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["album"].queryset = (
            Album.objects.filter(owner=user) if user else Album.objects.none()
        )

    def clean_audio_files(self):
        files = self.cleaned_data["audio_files"]
        for audio_file in files:
            try:
                validate_audio(audio_file)
            except ValidationError as error:
                raise forms.ValidationError(
                    f"{audio_file.name}: {'; '.join(error.messages)}"
                ) from error
        return files

    def clean(self):
        cleaned_data = super().clean()
        for key, image in self.files.items():
            if not key.startswith("cover_"):
                continue
            try:
                validate_image(image)
            except ValidationError as error:
                self.add_error(None, f"{image.name}: {'; '.join(error.messages)}")
        return cleaned_data


class TrackForm(forms.ModelForm):
    tags = forms.CharField(
        label="Теги",
        required=False,
        widget=forms.TextInput(
            attrs={
                "list": "music-tag-suggestions",
                "placeholder": "напр. джаз, вечер",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = Track
        fields = ["title", "artist", "album", "audio_file", "cover", "tags"]
        labels = {
            "title": "Название трека",
            "artist": "Исполнитель",
            "album": "Альбом",
            "audio_file": "Аудиофайл",
            "cover": "Обложка трека",
            "tags": "Теги",
        }
        widgets = {"cover": forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Tracks can only be added to albums owned by the current user.
        self.fields["album"].queryset = (
            Album.objects.filter(owner=user) if user else Album.objects.none()
        )
        self.fields["album"].empty_label = "Без альбома"
        if self.instance.pk:
            self.initial["tags"] = ", ".join(
                self.instance.track_tags.select_related("tag")
                .order_by("tag__name")
                .values_list("tag__name", flat=True)
            )

    def clean_tags(self):
        return services.normalize_tag_names(self.cleaned_data["tags"])


class AlbumForm(forms.ModelForm):
    class Meta:
        model = Album
        fields = ["title", "cover"]
        labels = {"title": "Название альбома", "cover": "Обложка"}


class PlaylistForm(forms.ModelForm):
    class Meta:
        model = Playlist
        fields = ["title", "description", "cover", "is_public"]
        labels = {
            "title": "Название плейлиста",
            "description": "Описание",
            "cover": "Обложка",
            "is_public": "Публичный плейлист",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class PlaylistTrackForm(forms.Form):
    track = forms.ModelChoiceField(
        queryset=Track.objects.none(),
        label="Трек",
        empty_label="Выберите трек",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["track"].queryset = Track.objects.select_related("owner", "album")


class CollaborativePlaylistForm(forms.Form):
    title = forms.CharField(label="Название", max_length=100)
    invitees = forms.ModelMultipleChoiceField(
        label="Пригласить подписок",
        queryset=User.objects.none(),
        required=True,
        widget=forms.SelectMultiple(attrs={"size": 5}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invitees"].queryset = User.objects.filter(
            pk__in=Follow.objects.filter(follower=user).values("following_id")
        ).order_by("username") if user else User.objects.none()


class MusicSettingsForm(forms.Form):
    show_now_playing = forms.BooleanField(
        label="Показывать, что я слушаю",
        required=False,
    )
    allow_join = forms.ChoiceField(
        label="Кто может присоединиться ко мне",
        choices=MusicSettings.JOIN_CHOICES,
    )


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(
        label="Оценка",
        choices=[(i, "★" * i) for i in range(5, 0, -1)],
        coerce=int,
    )
    text = forms.CharField(
        label="Отзыв",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
