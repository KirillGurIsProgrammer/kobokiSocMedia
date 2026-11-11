from django import forms


class MessageForm(forms.Form):
    text = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    file = forms.FileField(required=False)
