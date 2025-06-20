# authentication/forms.py

from django import forms
from authentication.models import Profile  
import re

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

#class SignUpForm(forms.Form):
    #email = forms.EmailField()
    #password = forms.CharField(widget=forms.PasswordInput)


class SignUpForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
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
    location = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.match(r'^[A-Za-z\s]+$', name):
            raise forms.ValidationError("Name can only contain letters and spaces.")
        return name
    
    def clean_confirm_password(self):
        password = self.cleaned_data.get("password")
        confirm_password = self.cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return confirm_password


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