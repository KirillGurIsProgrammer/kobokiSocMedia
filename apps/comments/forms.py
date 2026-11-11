from django import forms


class CommentForm(forms.Form):
    text = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 2}))
