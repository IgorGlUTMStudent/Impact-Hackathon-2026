from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator

from .models import Account, ChildProfile, normalize_email

# PasswordInput never re-renders the submitted value, so a PIN is not echoed back on a 422.
pin_field = forms.CharField(min_length=4, max_length=6, widget=forms.PasswordInput, validators=[RegexValidator(r"^\d{4,6}$", "PIN-ul are 4–6 cifre.")])


class LoginForm(AuthenticationForm):
    # One message whether the email exists or not (FR: no account enumeration).
    error_messages = {**AuthenticationForm.error_messages, "invalid_login": "Email sau parolă greșită."}


class SignupForm(forms.Form):
    email = forms.EmailField(max_length=254)
    display_name = forms.CharField(min_length=1, max_length=40)
    password = forms.CharField(widget=forms.PasswordInput, strip=False)

    def clean_email(self):
        email = normalize_email(self.cleaned_data["email"])
        if Account.objects.filter(email=email).exists():
            raise forms.ValidationError("Există deja un cont cu acest email.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password"):
            user = Account(email=cleaned.get("email", ""), display_name=cleaned.get("display_name", ""))
            try:
                validate_password(cleaned["password"], user)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned


class ChildForm(forms.ModelForm):
    class Meta:
        model = ChildProfile
        fields = ["nickname", "age_band", "avatar"]  # guardian comes from the session, never from the form


class RenameChildForm(forms.ModelForm):
    class Meta:
        model = ChildProfile
        fields = ["nickname"]


class PinSetForm(forms.Form):
    pin = pin_field
    pin_confirm = forms.CharField(max_length=6, widget=forms.PasswordInput)
    password = forms.CharField(widget=forms.PasswordInput, strip=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        if not self.user.check_password(self.cleaned_data["password"]):
            raise forms.ValidationError("Parola greșită.")
        return self.cleaned_data["password"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("pin") and cleaned.get("pin") != cleaned.get("pin_confirm"):
            self.add_error("pin_confirm", "PIN-urile nu coincid.")
        return cleaned


class PinGateForm(forms.Form):
    pin = pin_field  # the password is deliberately not accepted here (authorization.md exit contract)
