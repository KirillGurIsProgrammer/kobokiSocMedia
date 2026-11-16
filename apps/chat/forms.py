from django import forms


class MessageForm(forms.Form):
    text = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "chat-input",
                "placeholder": "Напишите сообщение…",
                "aria-label": "Текст сообщения",
            }
        ),
    )
    file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "chat-file-input", "aria-label": "Прикрепить файл"}
        ),
    )
