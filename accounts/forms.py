from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm


class ProfileEmailForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ('email',)
        widgets = {'email': forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'name@example.com'})}

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email address is already used by another account.')
        return email


class OTPVerificationForm(forms.Form):
    code = forms.CharField(min_length=6, max_length=6, widget=forms.TextInput(attrs={'autocomplete': 'one-time-code', 'inputmode': 'numeric', 'placeholder': '6-digit OTP'}))

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise forms.ValidationError('Enter the 6-digit OTP sent to your email.')
        return code


class NewPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['new_password2'].widget.attrs.update({'autocomplete': 'new-password'})
