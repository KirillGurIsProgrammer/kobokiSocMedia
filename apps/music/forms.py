from django import forms

from .models import Album, Playlist, Track


class TrackForm(forms.ModelForm):
    class Meta:
        model = Track
        fields = ["title", "artist", "album", "audio_file"]
        labels = {
            "title": "Название трека",
            "artist": "Исполнитель",
            "album": "Альбом",
            "audio_file": "Аудиофайл",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Tracks can only be added to albums owned by the current user.
        self.fields["album"].queryset = (
            Album.objects.filter(owner=user) if user else Album.objects.none()
        )


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
