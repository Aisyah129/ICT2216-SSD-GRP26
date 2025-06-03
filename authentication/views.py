# authentication/views.py

from django.contrib.auth.hashers import make_password, check_password
from authentication.models import User
from .forms import LoginForm, SignUpForm
import uuid
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404

# To log in a user
def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            try:
                user = User.objects.get(email=email)
                if check_password(password, user.password_hash):
                    request.session['user_id'] = user.user_id
                    return redirect('browse' if user.role == 'user' else 'admin_dashboard')
                else:
                    msg = "Invalid password"
            except User.DoesNotExist:
                msg = "User not found"
        else:
            msg = "Form not valid"

    return render(request, "accounts/login.html", {"form": form, "msg": msg})

# To register a new user
def register_user(request):
    form = SignUpForm(request.POST or None)
    msg = None

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data['email']
            raw_password = form.cleaned_data['password']
            hashed_password = make_password(raw_password)

            user = User(
                user_id=str(uuid.uuid4()),
                email=email,
                password_hash=hashed_password,
                role='user',
                is_premium=False,
                created_at=timezone.now()
            )
            user.save(using='default')

            request.session['user_id'] = user.user_id
            return redirect('user_dashboard')
        else:
            msg = "Form not valid"

    return render(request, "accounts/register.html", {"form": form, "msg": msg})


def user_dashboard(request):
    if 'user_id' not in request.session:
        return redirect('login')

    try:
        user = User.objects.get(user_id=request.session['user_id'])
        print("✅ USER EMAIL:", user.email)
    except User.DoesNotExist:
        print("❌ User not found for ID:", request.session['user_id'])
        return redirect('login')

    # Temporary placeholder
    matches = [
        {
            'name': 'Alex',
            'age': 26,
            'location': 'Singapore',
            'profile_pic': {'url': 'https://via.placeholder.com/300x200'}
        },
        {
            'name': 'Jamie',
            'age': 24,
            'location': 'Malaysia',
            'profile_pic': {'url': 'https://via.placeholder.com/300x200'}
        }
    ]

    return render(request, 'pages/browse.html', {
        'user': user,
        'matches': matches
    })


def admin_dashboard(request):
    users = User.objects.filter(role='user')  # only non-admins
    return render(request, 'accounts/admin_dashboard.html', {'users': users})
