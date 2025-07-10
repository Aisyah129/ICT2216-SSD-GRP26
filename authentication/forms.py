# authentication/forms.py

from django import forms
from django.contrib.auth.password_validation import validate_password
from authentication.models import Profile  
import re
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control form-control-alternative',
        'placeholder': 'Email'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-alternative',
        'placeholder': 'Password'
    }))
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())


class PasswordResetEmailForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-alternative',
            'placeholder': 'Enter your email'
        })
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())


class VerificationCodeForm(forms.Form):
    code = forms.CharField(
        label="Enter the 6-digit verification code",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-alternative',
            'placeholder': '123456'
        })
    )


class SetNewPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-alternative',
        'placeholder': 'New Password',
        'minlength': '8',
        'maxlength': '64',
        'pattern': '.{8,64}',
        'title': '8–64 characters'
    }), help_text="Use 8–64 characters; a memorable passphrase is best.")
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-alternative',
        'placeholder': 'Confirm Password',
        'minlength': '8',
        'maxlength': '64',
        'title': 'Repeat your password'
    }))

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('new_password')
        cpwd = cleaned_data.get('confirm_password')
        if pwd and cpwd and pwd != cpwd:
            raise forms.ValidationError("Passwords do not match.")
        # Validate length and common/breach via validators
        validate_password(pwd)
        return cleaned_data


class SignUpForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'minlength': '8',
            'maxlength': '64',
            'pattern': '.{8,64}',
            'title': '8–64 characters'
        }),
        help_text="Use 8–64 characters; a memorable passphrase is best."
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm Password',
            'minlength': '8',
            'maxlength': '64',
            'title': 'Repeat your password'
        })
    )

    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Name'
        })
    )

    age = forms.IntegerField(
        min_value=18,
        max_value=90,
        initial=18,
        widget=forms.NumberInput(attrs={
            'type': 'range',            # Slider input
            'min': '18',
            'max': '90',
            'step': '1',
            'class': 'form-control-range',
            'oninput': 'ageOutputId.value = this.value'  # For live display
        })
    )

    gender = forms.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    location = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Location'
        })
    )

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())


    def clean_email(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            #raise forms.ValidationError("Unable to process your request. Please try a different email.")
            self.add_error(None, "Unable to process your request. Please try again.")
        return email

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        
        # Check for at least one number
        if not re.search(r'\d', pwd):
            raise forms.ValidationError("Password must include at least one number.")
        
        # Check for at least one special character
        if not re.search(r'[^A-Za-z0-9]', pwd):
            raise forms.ValidationError("Password must include at least one special character.")
        
        validate_password(pwd)
        
        return pwd


    def clean_confirm_password(self):
        pwd  = self.cleaned_data.get('password')
        cpwd = self.cleaned_data.get('confirm_password')
        if pwd and cpwd and pwd != cpwd:
            raise forms.ValidationError("Passwords do not match.")
        return cpwd

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.match(r'^[A-Za-z\s]+$', name):
            raise forms.ValidationError("Name can only contain letters and spaces.")
        return name


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = Profile
        
        fields = [
            'age', 'gender', 'height_cm', 'sexual_orientation', 'pronouns',
            'body_type', 'location', 'education_level', 'occupation',
            'religion', 'ethnicity', 'politics', 'smoking', 'drinking',
            'drug_use', 'has_kids', 'wants_kids', 'zodiac_sign',
            'relationship_goals', 'hobbies', 'bio'
        ]

        widgets = {
            # style every widget with Bootstrap classes
            field: forms.TextInput(attrs={'class': 'form-control form-control-alternative'})
            for field in fields
        }

        widgets.update({
            'bio':     forms.Textarea(attrs={'rows': 4, 'class': 'form-control form-control-alternative'}),
            'hobbies': forms.Textarea(attrs={'rows': 3, 'class': 'form-control form-control-alternative'})
        })
