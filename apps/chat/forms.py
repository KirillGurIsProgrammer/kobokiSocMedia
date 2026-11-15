from django import forms


class MessageForm(forms.Form):
    text = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    file = forms.FileField(required=False)


class ConversationForm(forms.Form):
    kind = forms.ChoiceField(
        choices=(
            ("group", "Групповой чат"),
            ("channel", "Канал"),
        )
    )
    title = forms.CharField(max_length=120, label="Название")
    usernames = forms.CharField(
        required=False,
        label="Участники",
        help_text="Имена пользователей через запятую.",
    )
