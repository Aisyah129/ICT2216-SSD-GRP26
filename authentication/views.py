from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, SignUpForm
from django.contrib.auth import get_user_model

def login_view(request):
    form = LoginForm(request.POST or None)
    msg = 'Sign in with credentials'

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                if user.role == 'admin':
                    return redirect('admin_dashboard')
                else:
                    return redirect('browse')
            else:
                msg = 'Invalid credentials'
        else:
            msg = 'Error validating the form'

    return render(request, "accounts/login.html", {"form": form, "msg": msg})


def register_user(request):
    msg = 'Add your credentials'

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'user'
            user.save()
            login(request, user)
            return redirect('user_dashboard')
        else:
            msg = 'Form is not valid'
    else:
        form = SignUpForm()

    return render(request, "accounts/register.html", {"form": form, "msg": msg})


@login_required
def user_dashboard(request):
    return render(request, "accounts/user_dashboard.html")


@login_required
def admin_dashboard(request):
    User = get_user_model()
    users = User.objects.exclude(role='admin')  # Only show non-admins
    return render(request, 'accounts/admin_dashboard.html', {'users': users})
