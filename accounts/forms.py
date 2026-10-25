from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")   # passwords are added by UserCreationForm

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Give every input Bootstrap's styling class
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        """Reject an email that is already registered."""
        # Lowercase, so "Arib@Gmail.com" and "arib@gmail.com" count as the same address
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
