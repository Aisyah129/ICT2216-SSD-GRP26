# authentication/forms.py

from django import forms
from authentication.models import Profile  

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

class SignUpForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

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