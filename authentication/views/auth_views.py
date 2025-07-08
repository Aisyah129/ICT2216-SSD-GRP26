# authentication/views/auth_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login as auth_login, logout
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
import random, uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, Personalization
from authentication.models import User
from authentication.forms import LoginForm, PasswordResetEmailForm, SetNewPasswordForm, SignUpForm, VerificationCodeForm
from authentication.utils import log_action, has_permission

User = User

@csrf_protect
def login_view(request):
    if request.session.get('user_id'):
        try:
            user = User.objects.get(user_id=request.session['user_id'])
            if has_permission(user, "admin_dashboard_access"):
                return redirect('admin_dashboard')
            return redirect('browse')
        except User.DoesNotExist:
            pass

    form = LoginForm(request.POST or None)
    msg = None
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                auth_login(request, user)
                request.session['user_id'] = user.user_id
                log_action(user, "User logged in", "INFO", request)
                if has_permission(user, "admin_dashboard_access"):
                    return redirect('admin_dashboard')
                return redirect('browse')
            else:
                log_action(user, "Failed login - wrong password", "WARNING", request)
        except User.DoesNotExist:
            log_action(None, "Failed login - user not found", "WARNING", request)
        msg = "Incorrect email or password."
    return render(request, "accounts/login.html", {"form": form, "msg": msg})

@csrf_protect
def logout_view(request):
    if request.user.is_authenticated:
        log_action(request.user, "User logged out", "INFO", request)
    logout(request)
    return redirect('login')

def request_password_reset(request):
    form = PasswordResetEmailForm(request.POST or None)
    msg = None
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email=email)
            code = str(random.randint(100000, 999999))
            request.session.update({
                'reset_email': email,
                'reset_code': code,
                'reset_code_time': timezone.now().isoformat()
            })
            send_reset_code_email(email, code)
            log_action(user, "Requested password reset", "INFO", request)
            return redirect('verify_reset_code')
        except User.DoesNotExist:
            msg = "Invalid email address."
    return render(request, "accounts/password_reset_request.html", {"form": form, "msg": msg})

def send_reset_code_email(to_email, code):
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    subject = "🔐 Password Reset Code"
    content = Content("text/html", f"<p>Your password reset code is: <strong>{code}</strong></p>")
    message = Mail(from_email=from_email, subject=subject)
    message.add_content(content)
    personalization = Personalization()
    personalization.add_to(Email(to_email))
    message.add_personalization(personalization)
    try:
        sg.send(message)
    except Exception as e:
        print("❌ SendGrid error:", str(e))

def verify_reset_code(request):
    form = VerificationCodeForm(request.POST or None)
    msg = None
    if request.method == "POST" and form.is_valid():
        entered_code = form.cleaned_data['code']
        stored_code = request.session.get('reset_code')
        code_time_str = request.session.get('reset_code_time')
        email = request.session.get('reset_email')
        if stored_code and code_time_str and email:
            code_time = datetime.fromisoformat(code_time_str).replace(tzinfo=dt_timezone.utc)
            if timezone.now() - code_time > timedelta(minutes=1):
                new_code = str(random.randint(100000, 999999))
                request.session.update({
                    'reset_code': new_code,
                    'reset_code_time': timezone.now().isoformat()
                })
                send_reset_code_email(email, new_code)
                log_action(None, f"Reset code expired and resent to {email}", "INFO", request)
                msg = "Your code expired. A new one has been emailed."
            elif entered_code == stored_code:
                return redirect('set_new_password')
            else:
                msg = "Invalid verification code."
        else:
            msg = "No verification code found."
    return render(request, "accounts/password_reset_verify.html", {"form": form, "msg": msg})

def set_new_password(request):
    form = SetNewPasswordForm(request.POST or None)
    msg = None
    if request.method == "POST" and form.is_valid():
        email = request.session.get('reset_email')
        try:
            user = User.objects.get(email=email)
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            log_action(user, "Password reset successful", "CRITICAL", request)
            request.session.pop('reset_email', None)
            request.session.pop('reset_code', None)
            return redirect('login')
        except User.DoesNotExist:
            msg = "User not found."
    return render(request, "accounts/set_new_password.html", {"form": form, "msg": msg})

def send_verification_email(to_email, code):
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    subject = "Email Verification"
    content = Content("text/html", f"<p>Your verification code is: <strong>{code}</strong></p>")
    message = Mail(from_email=from_email, subject=subject)
    message.add_content(content)
    personalization = Personalization()
    personalization.add_to(Email(to_email))
    message.add_personalization(personalization)
    try:
        sg.send(message)
    except Exception as e:
        print("❌ Verification email error:", str(e))

def send_welcome_email(to_email, user_name):
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    subject = "🎉 Welcome!"
    content = Content("text/html", f"""
        <p>Hi {user_name},</p>
        <p>Welcome to our app! Your account has been created.</p>
        <p>Enjoy exploring!</p>""")
    message = Mail(from_email=from_email, subject=subject)
    message.add_content(content)
    personalization = Personalization()
    personalization.add_to(Email(to_email))
    message.add_personalization(personalization)
    try:
        sg.send(message)
    except Exception as e:
        print("❌ Welcome email error:", str(e))

def check_email(request):
    email = request.GET.get("email", "")
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({"exists": exists})

def register_user(request):
    form = SignUpForm(request.POST or None)
    msg = None
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            msg = "An account with this email already exists."
        else:
            data = {
                'email': email,
                'password': form.cleaned_data['password'],
                'name': form.cleaned_data['name'],
                'age': form.cleaned_data['age'],
                'gender': form.cleaned_data['gender'],
                'location': form.cleaned_data['location'],
            }
            verification_code = str(random.randint(100000, 999999))
            request.session.update({
                'registration_data': data,
                'verification_code': verification_code,
                'verification_code_time': timezone.now().isoformat()
            })
            send_verification_email(email, verification_code)
            return redirect('verify_email')
    return render(request, "accounts/register.html", {"form": form, "msg": msg})

def verify_email(request):
    msg = None
    if request.method == "POST":
        entered_code = request.POST.get("code")
        session_code = request.session.get("verification_code")
        code_time_str = request.session.get("verification_code_time")
        data = request.session.get("registration_data")
        if session_code and code_time_str and data:
            code_time = datetime.fromisoformat(code_time_str).replace(tzinfo=dt_timezone.utc)
            if timezone.now() - code_time > timedelta(minutes=1):
                new_code = str(random.randint(100000, 999999))
                request.session.update({
                    'verification_code': new_code,
                    'verification_code_time': timezone.now().isoformat()
                })
                send_verification_email(data['email'], new_code)
                msg = "Previous code expired. A new one has been sent."
            elif entered_code == session_code:
                user = User.objects.create_user(
                    email=data['email'],
                    password=data['password'],
                    role='user',
                    is_premium=False,
                    created_at=timezone.now()
                )
                from authentication.models import Profile
                Profile.objects.create(
                    profile_id=str(uuid.uuid4()),
                    user_id_fk=user,
                    name=data['name'],
                    age=data['age'],
                    gender=data['gender'],
                    location=data['location'],
                    created_at=timezone.now(),
                    last_updated=timezone.now()
                )
                send_welcome_email(user.email, data['name'])
                for key in ['registration_data', 'verification_code', 'verification_code_time']:
                    request.session.pop(key, None)
                auth_login(request, user)
                request.session['user_id'] = user.user_id
                return redirect('browse_one')
            else:
                msg = "Invalid verification code."
        else:
            msg = "Verification data missing or expired."
    return render(request, "accounts/verify.html", {"msg": msg})
