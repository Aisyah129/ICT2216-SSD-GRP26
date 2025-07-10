# authentication/forms.py

from django import forms
from django.contrib.auth.password_validation import validate_password
from authentication.models import Profile  
import re
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
import hashlib
import requests

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

def is_pwned_password(password):
    sha1pwd = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1pwd[:5]
    suffix = sha1pwd[5:]
    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            hashes = (line.split(':') for line in res.text.splitlines())
            for hash_suffix, count in hashes:
                if hash_suffix == suffix:
                    return True  # Found in breached DB
    except requests.RequestException:
        pass  # Optional: log or handle connection errors
    
    return False

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

        # Check if password has been breached
        if is_pwned_password(pwd):
            raise forms.ValidationError("This password has appeared in a known data breach. Please choose a different one.")
        
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
    
    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is None or age < 18 or age > 90:
            raise forms.ValidationError("Age must be between 18 and 90.")
        return age


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

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is None or age < 18 or age > 90:
            raise forms.ValidationError("Age must be between 18 and 90.")
        return age

    def clean_height_cm(self):
        h = self.cleaned_data.get('height_cm')
        if h is None or h < 100 or h > 250:
            raise forms.ValidationError("Height must be between 100cm and 250cm.")
        return h

    def clean_location(self):
        loc = self.cleaned_data.get('location', '').strip()
        if loc and len(loc) > 50:
            raise forms.ValidationError("Location must be under 50 characters.")
        return loc

    def clean_occupation(self):
        occ = self.cleaned_data.get('occupation', '').strip()
        if occ and not re.match(r'^[A-Za-z0-9\s\-\.\&]{2,100}$', occ):
            raise forms.ValidationError("Occupation can only contain letters, numbers, spaces, and - . & (2–100 chars).")
        return occ

    def clean_hobbies(self):
        h = self.cleaned_data.get('hobbies', '').strip()
        if h and (len(h) > 200 or not re.match(r'^[A-Za-z,\s]+$', h)):
            raise forms.ValidationError("Hobbies must be under 200 chars and only letters, commas, and spaces.")
        return h

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '').strip()
        if len(bio) > 500:
            raise forms.ValidationError("Bio must be under 500 characters.")
        return bio

