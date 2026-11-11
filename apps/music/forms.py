from django import forms

from .models import Album, Track


class TrackForm(forms.ModelForm):
    class Meta:
        model = Track
        fields = ["title", "artist", "album", "audio_file"]

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


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(
        label="Rating",
        choices=[(i, "★" * i) for i in range(5, 0, -1)],
        coerce=int,
    )
    text = forms.CharField(
        label="Review",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
