from django import forms


class ConfigEditForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 28, "spellcheck": "false"}),
        required=False,
    )
    create_backup = forms.BooleanField(required=False, initial=True)
