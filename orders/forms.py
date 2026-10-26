import re

from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    # Declared here so the form accepts "017-1234-5678" or "+880 1712 345678" (longer than 11);
    # clean_phone() then turns it into the 11 digits the model stores.
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"placeholder": "01XXXXXXXXX"}))

    class Meta:
        model = Order
        fields = ["full_name", "phone", "address", "city"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_phone(self):
        """Accept only Bangladeshi mobile numbers: 11 digits, starting 013–019."""
        phone = self.cleaned_data["phone"].replace(" ", "").replace("-", "")
        phone = re.sub(r"^\+?88", "", phone)   # drop the country code: +8801712345678 → 01712345678
        if not re.fullmatch(r"01[3-9]\d{8}", phone):
            raise forms.ValidationError("Enter a valid Bangladeshi mobile number (e.g. 01712345678).")
        return phone
