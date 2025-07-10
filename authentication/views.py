# authentication/views.py

# ✦ Standard library
import json
import os
import random
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Optional  # ← used in a few type-hints

# ✦ Third-party libraries
import boto3
import certifi
import iso8601
import stripe
import magic
from pymongo import MongoClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, Personalization
from functools import lru_cache
from urllib.parse import quote

from cryptography.fernet import InvalidToken
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from base64 import b64encode, b64decode

# ✦ Django core
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.text import Truncator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.cache import never_cache
from django.templatetags.static import static
from sklearn.metrics.pairwise import cosine_similarity
from axes.handlers.proxy import AxesProxyHandler
import numpy as np

from django.db import transaction

# ✦ Django ORM
from django.db.models import Q

# ✦ Project-local
from authentication.models import *
from .utils import log_action
from .forms import (
    LoginForm,
    PasswordResetEmailForm,
    SetNewPasswordForm,
    SignUpForm,
    VerificationCodeForm,
)

from .models import User, Report
from authentication.decorators import user_only
from .utils import has_permission
from authentication.middleware import get_client_ip
from authentication.models import Profile
from .forms import ProfileUpdateForm
from authentication.models import Language
from authentication.models import ProfileImage
from .forms import PreferencesForm
from authentication.models import Preferences
from authentication.models import PreferencesGender
from authentication.models import Like

from authentication.models import (
    Preferences,
    PreferencesBodyType,
    PreferencesEducation,
    PreferencesReligion,
    PreferencesEthnicity,
    PreferencesPolitics,
    PreferencesSmoking,
    PreferencesDrinking,
    PreferencesDrug,
    PreferencesHasKids,
    PreferencesWantsKids,
    PreferencesLanguage,
    PreferencesZodiac,
    PreferencesRelationship
)
from .forms import ReportForm

os.environ['SSL_CERT_FILE'] = certifi.where()


# AuthController

def is_admin(user):
    return user.is_authenticated and has_permission(user, "view_admin_dashboard")


@csrf_exempt
def test_login(request):
    from django.contrib.auth import authenticate, login
    user = authenticate(request, username="user1@example.com", password="user1")
    if user:
        login(request, user)
        return redirect('/profile/')
    return HttpResponse("Test login failed", status=401)

# AuthController
def login_view(request):
    if request.session.get('user_id'):
        # Already logged in — redirect based on role
        try:
            user = User.objects.get(user_id=request.session['user_id'])
            if has_permission(user, "admin_dashboard_access"):
                return redirect('admin_dashboard')
            return redirect('browse')
        except User.DoesNotExist:
            pass  # fall through to login screen if session is stale

    form = LoginForm(request.POST or None)
    msg = None

    if request.method == "POST":

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # 🔒 Check lock AFTER valid form, BEFORE querying user
            if AxesProxyHandler.is_locked(request):
                msg = "🚫 Too many failed login attempts. Please try again later."
                return render(request, "accounts/login.html", {
                    "form": form,
                    "msg": msg,
                    "session_timeout": False
                })

            # Trigger Axes logging here
            authenticate(request, username=email, password=password)

            try:
                user = User.objects.get(email=email)
                if user.check_password(password):
                    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    request.session['user_id'] = user.user_id

                    # When user logs in
                    request.session['ip'] = get_client_ip(request)
                    request.session['ua'] = request.META.get('HTTP_USER_AGENT')

                    # ✅ LOG success
                    log_action(user, "User logged in", "INFO", request)

                    if has_permission(user, "admin_dashboard_access"):
                        return redirect('admin_dashboard')
                    return redirect('browse')

                else:
                    # ✅ LOG wrong password
                    log_action(user, "Failed login attempt (wrong password)", "WARNING", request)
                    msg = "Incorrect email or password."
            except User.DoesNotExist:
                # ✅ LOG invalid email (no such user)
                log_action(None, "Failed login - user not found", "WARNING", request, metadata={"email": email})
                msg = "Incorrect email or password."
        else:
            msg = "Please correct the errors below."
    session_timeout = False
    for message in messages.get_messages(request):
        if message.message == "timeout":
            session_timeout = True
            break
    return render(request, "accounts/login.html", {
        "form": form,
        "msg": msg,
        "session_timeout": session_timeout
    })


# AuthController
@csrf_protect
def logout_view(request):
    if request.user.is_authenticated:
        log_action(request.user, "User logged out", "INFO", request)
    logout(request)
    return redirect('login')


# AuthController
def request_password_reset(request):
    form = PasswordResetEmailForm(request.POST or None)
    msg = None

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email=email)
            code = str(random.randint(100000, 999999))
            request.session['reset_email'] = email
            request.session['reset_code'] = code
            request.session['reset_code_time'] = timezone.now().isoformat()
            send_reset_code_email(email, code)
            log_action(user, "Requested password reset", "INFO", request)  # ✅ Log password reset requested
            # return redirect('verify_reset_code')
        except User.DoesNotExist:
            # msg = "Invalid email address."
            # Fake code, do NOT send email
            request.session['reset_email'] = email
            request.session['reset_code'] = None  # Or '000000' if you want consistency
            request.session['reset_code_time'] = timezone.now().isoformat()
            # Optional: Log attempt without revealing existence
            log_action(None, f"Password reset attempt for non-existent email: {email}", "WARNING", request)

        # In all cases: redirect to verification page
        return redirect('verify_reset_code')

    return render(request, "accounts/password_reset_request.html", {"form": form, "msg": msg})


# AuthController
def send_reset_code_email(to_email, code):
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    subject = "🔐 Password Reset Code for Ai Stead Mai"
    content = Content("text/html", f"<p>Your password reset code is: <strong>{code}</strong></p>")

    message = Mail()
    message.from_email = from_email
    message.subject = subject
    message.add_content(content)

    personalization = Personalization()
    personalization.add_to(Email(to_email))
    message.add_personalization(personalization)

    try:
        response = sg.send(message)
        print("✅ Password reset code sent:", response.status_code)
    except Exception as e:
        print("❌ SendGrid error:", str(e))


# AuthController
def verify_reset_code(request):
    if request.session.get('user_id'):
        return redirect('browse')  # Already logged in

    form = VerificationCodeForm(request.POST or None)
    msg = None

    if request.method == "POST":
        if not form.is_valid():
            msg = "Please try again."
        else:
            entered_code = form.cleaned_data['code']
            stored_code = request.session.get('reset_code')
            code_time_str = request.session.get('reset_code_time')
            email = request.session.get('reset_email')

            if stored_code and code_time_str and email:
                code_time = datetime.fromisoformat(code_time_str).replace(tzinfo=dt_timezone.utc)

                if timezone.now() - code_time > timedelta(minutes=1):
                    # Code expired — generate and send new one
                    new_code = str(random.randint(100000, 999999))
                    request.session['reset_code'] = new_code
                    request.session['reset_code_time'] = timezone.now().isoformat()

                    send_reset_code_email(email, new_code)
                    log_action(None, f"Reset code expired and new one sent to {email}", "INFO", request)

                    msg = "Your code expired. A new one has been emailed to you."
                elif entered_code == stored_code:
                    try:
                        user = User.objects.get(email=email)
                        log_action(user, "Verified reset code", "INFO", request)
                    except User.DoesNotExist:
                        log_action(None, f"Reset code verified but user {email} not found", "WARNING", request)

                    return redirect('set_new_password')
                else:
                    log_action(None, f"Failed reset code attempt for {email}", "WARNING", request)
                    msg = "Invalid verification code."
            else:
                msg = "Please try again."

    return render(request, "accounts/password_reset_verify.html", {"form": form, "msg": msg})


# AuthController
def set_new_password(request):
    form = SetNewPasswordForm(request.POST or
                              None)
    msg = None

    if request.method == "POST" and form.is_valid():
        email = request.session.get('reset_email')
        try:
            user = User.objects.get(email=email)
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            log_action(user, "Password reset successful", "CRITICAL", request)
            # Clear session
            del request.session['reset_email']
            del request.session['reset_code']
            return redirect('login')
        except User.DoesNotExist:
            msg = "User not found."
            log_action(None, f"Password reset failed - user not found: {email}", "CRITICAL", request)

    return render(request, "accounts/set_new_password.html", {"form": form, "msg": msg})


# AuthController
def send_verification_email(to_email, code):
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    subject = "Ai Stead Mai Email Verification"
    content = Content("text/html", f"<p>Hello! Your verification code is: <strong>{code}</strong></p>")

    message = Mail()
    message.from_email = from_email
    message.subject = subject
    message.add_content(content)

    personalization = Personalization()
    personalization.add_to(Email(to_email))
    message.add_personalization(personalization)

    try:
        response = sg.send(message)
        print("✅ Email sent with status code:", response.status_code)
    except Exception as e:
        print("❌ SendGrid error:", str(e))


# AuthController
def send_welcome_email(to_email, user_name):
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    subject = "🎉 Welcome to Ai Stead Mai!"
    content = Content("text/html", f"""
        <p>Hi {user_name},</p>
        <p>Welcome to <strong>Ai Stead Mai</strong>! Your account has been successfully created.</p>
        <p>You can now start exploring matches and connect with others!</p>
        <br>
        <p>Cheers,<br>The Ai Stead Mai Team</p>
    """)

    message = Mail()
    message.from_email = from_email
    message.subject = subject
    message.add_content(content)

    personalization = Personalization()
    personalization.add_to(Email(to_email))
    message.add_personalization(personalization)

    try:
        response = sg.send(message)
        print("✅ Welcome email sent:", response.status_code)
    except Exception as e:
        print("❌ SendGrid welcome email error:", str(e))


User = get_user_model()


# AuthController
def check_email(request):
    email = request.GET.get("email", "")
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({"exists": exists})


# AuthController
def register_user(request):
    form = SignUpForm(request.POST or None)
    msg = None

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']

        # ✅ Check if email already exists
        if User.objects.filter(email=email).exists():
            msg = "An account with this email already exists."
            log_action(None, f"Duplicate registration attempt for {email}", "WARNING", request)
            return render(request, "accounts/register.html", {"form": form, "msg": msg})

        # Temporarily store registration data in session
        request.session['registration_data'] = {
            'email': email,
            'password': form.cleaned_data['password'],
            'name': form.cleaned_data['name'],
            'age': form.cleaned_data['age'],
            'gender': form.cleaned_data['gender'],
            'location': form.cleaned_data['location'],
        }

        # Generate and store verification code
        verification_code = str(random.randint(100000, 999999))
        request.session['verification_code'] = verification_code
        request.session['verification_code_time'] = timezone.now().isoformat()

        log_action(None, f"Registration initiated for {email}", "INFO", request)
        send_verification_email(email, verification_code)

        return redirect('verify_email')

    elif request.method == "POST":
        log_action(None, "Failed registration attempt", "WARNING", request, metadata=form.errors.get_json_data())

    return render(request, "accounts/register.html", {"form": form, "msg": msg})


# AuthController
# VERIFY: confirm code, then store to DB
def verify_email(request):
    if request.session.get('user_id'):
        return redirect('browse')  # Already logged in

    msg = None

    if request.method == "POST":
        entered_code = request.POST.get("code")
        session_code = request.session.get("verification_code")
        # code_time_str = request.session['verification_code_time'] = timezone.now().isoformat()
        code_time_str = request.session.get("verification_code_time")
        data = request.session.get("registration_data")

        if session_code and code_time_str and data:
            code_time = datetime.fromisoformat(code_time_str).replace(tzinfo=dt_timezone.utc)

            if timezone.now() - code_time > timedelta(minutes=1):
                # Code expired — generate and resend
                new_code = str(random.randint(100000, 999999))
                request.session['verification_code'] = new_code
                request.session['verification_code_time'] = timezone.now().isoformat()

                send_verification_email(data['email'], new_code)
                msg = "Previous code expired. A new one has been sent to your email."
            elif entered_code == session_code:
                # ✅ Register user and log them in
                user = User.objects.create_user(
                    email=data['email'],
                    password=data['password'],
                    role='user',
                    is_premium=False,
                    created_at=timezone.now()
                )

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

                # Clear session data after success
                for key in ['registration_data', 'verification_code', 'verification_code_time']:
                    request.session.pop(key, None)

                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                request.session['user_id'] = user.user_id
                log_action(user, "User account created and verified", "INFO", request)

                return redirect('browse_one')
            else:
                msg = "Invalid verification code."
        else:
            msg = "Verification code missing or expired. Please register again."

    return render(request, "accounts/verify.html", {"msg": msg})


# USER DASHBOARD — use @login_required
@never_cache
@login_required
# MatchController
def user_dashboard(request):
    user = request.user  # automatically available
    print("✅ USER EMAIL:", user.email)

    matches = [
        {'name': 'Alex', 'age': 26, 'location': 'Singapore',
         'profile_pic': {'url': 'https://via.placeholder.com/300x200'}},
        {'name': 'Jamie', 'age': 24, 'location': 'Malaysia',
         'profile_pic': {'url': 'https://via.placeholder.com/300x200'}}
    ]

    return render(request, 'pages/browse.html', {
        'user': user,
        'matches': matches
    })


# ProfileController
@never_cache
@login_required
def profile_view(request):
    profile = get_object_or_404(Profile, user_id_fk=request.user)

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Profile updated successfully.")
            return redirect('profile')
        else:
            messages.error(request, "❌ Please correct the errors below.")
    else:
        form = ProfileUpdateForm(instance=profile)

    primary_image = profile.profileimage_set.filter(is_primary=True).first()
    primary_image_url = get_safe_profile_image_url(primary_image, True)
    all_images = [
        {
            "id": img.image_id,
            "url": get_safe_profile_image_url(img, True),
            "is_primary": img.is_primary
        }
        for img in profile.profileimage_set.order_by('-uploaded_at')
    ]
    all_languages = Language.objects.all()
    selected_language_ids = list(profile.languages.values_list('language_id_fk__language_id', flat=True))

    return render(request, "pages/profile.html", {
        "form": form,
        "profile": profile,
        "primary_image": primary_image_url,
        "images": all_images,
        "all_languages": all_languages,
        "selected_language_ids": selected_language_ids,
    })


MAX_IMAGES = 6  # ← adjust if needed


# ------------------------------------------------------------------
#  Upload profile image                                   (updated)
# ------------------------------------------------------------------
# ProfileController
@login_required
@require_POST
def upload_profile_image(request):
    """
     Upload profile image to private S3 and store only the filename.Add commentMore actions
    - Max limit enforced
    - Always ensure 1 primary
    - Returns public ImageKit URL for frontend use
    """
    file = request.FILES.get("image")
    if not file:
        log_action(request.user, "Failed image upload - no image provided", "WARNING", request)
        return JsonResponse({"success": False, "error": "No image uploaded"}, status=400)

    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif']
    extension = file.name.split('.')[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return JsonResponse({"success": False, "error": "Invalid file extension."}, status=400)

    # Read a sample of the file to guess its real type
    file_sample = file.read(2048)
    file.seek(0)  # rewind so S3 still works

    mime_type = magic.from_buffer(file_sample, mime=True)
    if mime_type not in ['image/jpeg', 'image/png', 'image/gif']:
        return JsonResponse({"success": False, "error": "Invalid MIME type."}, status=400)

    profile = request.user.profile

    # ───────── 1) Check image limit ──────────
    current_count = ProfileImage.objects.filter(profile_id_fk=profile).count()
    if current_count >= MAX_IMAGES:
        log_action(request.user, "Rejected profile image - image limit reached", "WARNING", request, metadata={
            "current_count": current_count,
            "max_limit": MAX_IMAGES
        })
        return JsonResponse({"success": False, "error": f"Limit of {MAX_IMAGES} images reached"}, status=400)

    # ───────── 2) Upload to S3 ──────────
    extension = file.name.split('.')[-1]
    filename = f"profile_{profile.profile_id}_{uuid.uuid4()}.{extension}"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )

    s3.upload_fileobj(
        file,
        settings.AWS_STORAGE_BUCKET_NAME,
        filename,
        ExtraArgs={"ACL": "private", "ContentType": file.content_type}
    )

    want_primary = request.POST.get("is_primary") in ("1", "true", "on")

    # ───────── 3) Ensure ONE primary ──────────
    has_primary = ProfileImage.objects.filter(profile_id_fk=profile, is_primary=True).exists()

    if want_primary or not has_primary:
        ProfileImage.objects.filter(profile_id_fk=profile).update(is_primary=False)
        primary_flag = True
    else:
        primary_flag = False

    # ───────── 4) Save DB record (only filename) ──────────
    new_image = ProfileImage.objects.create(
        image_id=str(uuid.uuid4()),
        profile_id_fk=profile,
        image_url=filename,  # ✅ only the filename!
        is_primary=primary_flag,
        uploaded_at=timezone.now(),
    )

    log_action(request.user, "Uploaded new profile image", "INFO", request, metadata={
        "filename": filename,
        "content_type": file.content_type,
        "is_primary": primary_flag
    })

    # Generate ImageKit public URL
    public_url = get_safe_profile_image_url(new_image, request.user.is_premium)

    return JsonResponse({"success": True, "image_url": public_url})


# ProfileController
# 🟩 Get all profile images for this user (JSON)
@login_required
def profile_images_json(request):
    profile = request.user.profile
    images = ProfileImage.objects.filter(profile_id_fk=profile).order_by('-uploaded_at')

    return JsonResponse([
        {
            "image_id": str(img.image_id),  # ensure string for JS
            "image_url": get_safe_profile_image_url(img, request.user.is_premium),
            "is_primary": img.is_primary,
        }
        for img in images
    ], safe=False)


# ProfileController
# 🟩 Set selected image as primary
@login_required
@require_POST
def set_primary_image(request, pk):
    profile = request.user.profile

    # Unset all existing
    ProfileImage.objects.filter(profile_id_fk=profile).update(is_primary=False)

    # Set new primary
    updated = ProfileImage.objects.filter(profile_id_fk=profile, pk=pk).update(is_primary=True)

    if updated:
        log_action(request.user, f"Set image {pk} as primary", "INFO", request)

    return JsonResponse({"success": bool(updated)})


# ProfileController
# 🟥 Delete selected image from DB and S3
@login_required
@require_http_methods(["DELETE"])
def delete_profile_image(request, pk):
    try:
        profile = request.user.profile
        image = ProfileImage.objects.get(profile_id_fk=profile, pk=pk)

        # Assume image_url is just the filename, e.g., "profile_abc123.jpg"Add commentMore actions
        filename = image.image_url.strip("/")

        # Delete from S3 (private bucket)
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=filename)

        # Delete from DB
        image.delete()
        log_action(request.user, f"Deleted profile image {pk}", "INFO", request, metadata={"filename": filename})
        return JsonResponse({"success": True})

    except ProfileImage.DoesNotExist:
        log_action(request.user, f"Tried to delete non-existent profile image {pk}", "WARNING", request)
        return JsonResponse({"success": False, "error": "Image not found"}, status=404)


# ADMIN DASHBOARD
@never_cache
@login_required
@user_passes_test(is_admin)
# AdminController
def admin_dashboard(request):
    if not has_permission(request.user, "admin_dashboard_access"):
        return redirect('browse')

    # 🟢 Users queryset
    users_qs = User.objects.all().order_by('-created_at')
    # 🟢 Logs queryset
    logs_qs = ActionLog.objects.order_by('-timestamp')

    # 🔍 Filter logs
    user_email = request.GET.get('user_email')
    severity = request.GET.get('severity')
    if user_email:
        logs_qs = logs_qs.filter(user__email__icontains=user_email)
    if severity:
        logs_qs = logs_qs.filter(severity=severity)

    # 🔍 Filter users
    search_user = request.GET.get('search_user')
    role_filter = request.GET.get('role')
    premium_filter = request.GET.get('is_premium')

    if search_user:
        users_qs = users_qs.filter(email__icontains=search_user)
    if role_filter in ['user', 'admin']:
        users_qs = users_qs.filter(role=role_filter)
    if premium_filter in ['true', 'false']:
        users_qs = users_qs.filter(is_premium=(premium_filter == 'true'))

    # 🆕 Paginate users (10 per page)
    user_paginator = Paginator(users_qs, 10)
    users = user_paginator.get_page(request.GET.get('page_users'))

    # 📄 Paginate logs (10 per page)
    log_paginator = Paginator(logs_qs, 10)
    logs = log_paginator.get_page(request.GET.get("page"))

    return render(request, 'accounts/admin_dashboard.html', {
        'users': users,
        'logs': logs,
        'search_user': search_user,
        'role_filter': role_filter,
        'premium_filter': premium_filter,
        'severity': severity,
        'user_email': user_email,
    })


# ProfileController
def get_primary_image(profile_id):
    return ProfileImage.objects.filter(profile_id_fk=profile_id, is_primary=1).first()


# ProfileController
def get_blurred_image_url(original_url):
    if not original_url:
        return None

    filename = original_url.split("/")[-1]

    # Compose ImageKit URL
    return f"{settings.IMAGEKIT_URL_ENDPOINT}tr:bl-20/{quote(filename)}"


# ProfileController
def get_safe_profile_image_url(image, is_premium):
    default_url = '/static/images/default-avatar.jpg'
    blurred_default_url = '/static/images/blurred-default-avatar.jpg'

    if not image:
        return default_url if is_premium else blurred_default_url

    filename = image.image_url.lstrip("/")
    print(image.image_url)

    if is_premium:
        return f"{settings.IMAGEKIT_URL_ENDPOINT}{quote(filename)}"
    else:
        return f"{settings.IMAGEKIT_URL_ENDPOINT}tr:bl-20/{quote(filename)}"


@never_cache
@login_required
@user_only
# MatchController
def likes_page(request):
    user = request.user
    current_user_id = user.user_id
    tab = request.GET.get('tab', 'incoming')
    page_number = request.GET.get('page', 1)

    incoming_likes = []
    outgoing_likes = []

    match_popup = request.session.pop('match_popup_likes', None)

    if tab == 'incoming':
        incoming_likes_raw = Like.objects.filter(
            liked_user_id=user,
            like_status='liked'
        ).order_by('-liked_at')

        for like in incoming_likes_raw:
            # Skip if mutual match already exists
            if Like.objects.filter(liker_user_id=user, liked_user_id=like.liker_user_id).exists():
                continue

            try:
                profile = Profile.objects.get(user_id_fk=like.liker_user_id)
                image = get_primary_image(profile.profile_id)
                incoming_likes.append({
                    'id': like.liker_user_id.user_id,
                    'name': profile.name if user.is_premium else None,
                    'age': profile.age if user.is_premium else None,
                    'liked_date': like.liked_at if user.is_premium else None,
                    'image_url': get_safe_profile_image_url(image, user.is_premium),
                    'gender': profile.gender if user.is_premium else None,
                    'location': profile.location if user.is_premium else None,
                    'pronouns': profile.pronouns if user.is_premium else None,
                    'sexual_orientation': profile.sexual_orientation if user.is_premium else None,
                    'zodiac_sign': profile.zodiac_sign if user.is_premium else None,
                    'smoking': profile.smoking if user.is_premium else None,
                    'drinking': profile.drinking if user.is_premium else None,
                    'drug_use': profile.drug_use if user.is_premium else None,
                    'has_kids': profile.has_kids if user.is_premium else None,
                    'wants_kids': profile.wants_kids if user.is_premium else None,
                    'education_level': profile.education_level if user.is_premium else None,
                    'occupation': profile.occupation if user.is_premium else None,
                    'religion': profile.religion if user.is_premium else None,
                    'politics': profile.politics if user.is_premium else None,
                    'ethnicity': profile.ethnicity if user.is_premium else None,
                    'height_cm': profile.height_cm if user.is_premium else None,
                    'body_type': profile.body_type if user.is_premium else None,
                    'hobbies': profile.hobbies if user.is_premium else None,
                    'relationship_goals': profile.relationship_goals if user.is_premium else None,
                    'bio': profile.bio if user.is_premium else None,
                })
            except Profile.DoesNotExist:
                continue

        paginator = Paginator(incoming_likes, 6)
        page_obj = paginator.get_page(page_number)

        return render(request, 'pages/likes.html', {
            'viewer': user,
            'incoming_likes': page_obj,
            'outgoing_likes': [],
            'active_tab': 'incoming',
            'page_obj': page_obj,
            'match_popup': match_popup
        })

    elif tab == 'outgoing':
        outgoing_likes_raw = Like.objects.filter(liker_user_id=user, like_status='liked').order_by('-liked_at')

        for like in outgoing_likes_raw:
            # Skip if mutual match already exists
            if Like.objects.filter(liker_user_id=like.liked_user_id, liked_user_id=user).exists():
                continue

            try:
                profile = Profile.objects.get(user_id_fk=like.liked_user_id)
                image = get_primary_image(profile.profile_id)
                outgoing_likes.append({
                    'id': like.liked_user_id.user_id,
                    'name': profile.name,
                    'age': profile.age,
                    'liked_date': like.liked_at,
                    'image_url': f"{settings.IMAGEKIT_URL_ENDPOINT}{image.image_url}" if image else settings.STATIC_URL + 'images/default-avatar.jpg',
                    'gender': profile.gender,
                    'location': profile.location,
                    'pronouns': profile.pronouns,
                    'sexual_orientation': profile.sexual_orientation,
                    'zodiac_sign': profile.zodiac_sign,
                    'smoking': profile.smoking,
                    'drinking': profile.drinking,
                    'drug_use': profile.drug_use,
                    'has_kids': profile.has_kids,
                    'wants_kids': profile.wants_kids,
                    'education_level': profile.education_level,
                    'occupation': profile.occupation,
                    'religion': profile.religion,
                    'politics': profile.politics,
                    'ethnicity': profile.ethnicity,
                    'height_cm': profile.height_cm,
                    'body_type': profile.body_type,
                    'hobbies': profile.hobbies,
                    'relationship_goals': profile.relationship_goals,
                    'bio': profile.bio
                })
            except Profile.DoesNotExist:
                continue

        paginator = Paginator(outgoing_likes, 6)
        page_obj = paginator.get_page(page_number)

        return render(request, 'pages/likes.html', {
            'viewer': user,
            'incoming_likes': [],
            'outgoing_likes': page_obj,
            'active_tab': 'outgoing',
            'page_obj': page_obj,
            'match_popup': match_popup
        })


@never_cache
@login_required
# BillingController
def upgrade_premium(request):
    plans = [
        {'id': 'week', 'name': '1 Week', 'price': 4.99, 'description': 'Short-term access to premium features'},
        {'id': 'month', 'name': '1 Month', 'price': 9.99, 'description': 'Unlock premium features for a month'},
        {'id': 'quarter', 'name': '3 Months', 'price': 24.99, 'description': 'Save more with a 3-month plan'},
    ]
    log_action(request.user, "Visited premium upgrade page", "INFO", request)  # not working currently
    return render(request, 'accounts/upgrade_premium.html', {'plans': plans})


# BillingController
def checkout_premium(request, plan_id):
    return HttpResponse(f"Stripe checkout for plan: {plan_id}")


# --- MongoDB Connection ---
@lru_cache
def mongo():
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB]


COL = mongo().messages  # <-- Each message is its own document


# MessageController
def decrypt_aes_gcm(cipher_b64, nonce_b64):
    try:
        aesgcm = AESGCM(settings.AES_KEY)
        nonce = b64decode(nonce_b64)
        ciphertext = b64decode(cipher_b64)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()
    except Exception as e:
        return "[decryption failed]"


# MessageController
def fetch_messages(match, limit=None):
    q = {"match_id": str(match.match_id)}
    cursor = COL.find(q).sort("sent_at", 1)
    if limit:
        cursor = cursor.limit(limit)

    messages = []

    for doc in cursor:
        raw = doc.get("ciphertext", "")
        nonce = doc.get("nonce", "")

        try:
            raw = doc.get("ciphertext", "")
            nonce = doc.get("nonce", "")
            doc["ciphertext"] = decrypt_aes_gcm(raw, nonce) if raw and nonce else "[missing ciphertext]"
        except Exception:
            doc["ciphertext"] = "[error]"

        messages.append(doc)

    return messages


# MessageController
def append_message(match, sender_id, text):
    # Encrypt the plaintext on the backend
    aesgcm = AESGCM(settings.AES_KEY)
    nonce = os.urandom(12)  # AES-GCM standard nonce size
    ciphertext = aesgcm.encrypt(nonce, text.encode(), None)

    cipher_b64 = b64encode(ciphertext).decode()
    nonce_b64 = b64encode(nonce).decode()

    msg = {
        "match_id": str(match.match_id),
        "message_id": str(uuid.uuid4()),
        "sender_user_id": sender_id,
        "ciphertext": cipher_b64,
        "nonce": nonce_b64,
        "sent_at": timezone.now().isoformat(timespec="seconds"),
        "is_read": False,
        "encryption_meta": {"alg": "AES-GCM", "version": 1},
    }

    COL.insert_one(msg)
    return msg


# MessageController
def mark_read(match, reader_id):
    COL.update_many(
        {
            "match_id": str(match.match_id),
            "sender_user_id": {"$ne": reader_id},
            "is_read": False
        },
        {"$set": {"is_read": True}}
    )


# MessageController
def get_conversations_for(user):
    # 1️⃣ SQL matches that involve me
    sql_matches = (
        Match.objects
        .filter(is_active=1)
        .filter(Q(user1_id=user.user_id) | Q(user2_id=user.user_id))
        .values("match_id", "user1_id", "user2_id")
    )
    match_ids = [str(m["match_id"]) for m in sql_matches]

    # 2️⃣ unread counts in Mongo
    pipeline = [
        {"$match": {
            "match_id": {"$in": match_ids},
            "sender_user_id": {"$ne": str(user.user_id)},
            "is_read": False
        }},
        {"$group": {"_id": "$match_id", "unread": {"$sum": 1}}},
    ]
    unread_map = {d["_id"]: d["unread"] for d in COL.aggregate(pipeline)}

    # 3️⃣ build sidebar data
    conversations = []
    for m in sql_matches:
        other_uuid = m["user2_id"] if m["user1_id"] == user.user_id else m["user1_id"]
        # ▸ grab display name & primary image
        try:
            profile = Profile.objects.only("name").get(user_id_fk__user_id=other_uuid)
            display = profile.name or "Unknown"
        except Profile.DoesNotExist:
            display = "Unknown"

        # primary image (may be None)
        img = (ProfileImage.objects
               .only("image_url")
               .filter(profile_id_fk=profile, is_primary=1)
               .first())
        img_url = (
            f"{settings.IMAGEKIT_URL_ENDPOINT}{img.image_url}"
            if img else settings.STATIC_URL + "/static/images/default-avatar.jpg"
        )

        conversations.append({
            "user_id": other_uuid,
            "name": display,
            "avatar": img_url,
            "unread": unread_map.get(str(m["match_id"]), 0),
        })

    # sort: unread first, then alpha
    conversations.sort(key=lambda c: (-c["unread"], c["name"].lower()))
    return conversations


# add near messages_with
@never_cache
@login_required
@user_only
def messages_home(request):
    convos = get_conversations_for(request.user)
    if convos:
        # jump straight into the 1st conversation
        return redirect("messages_with", user_id=convos[0]["user_id"])
    # no matches yet – render same template with placeholders
    return render(request, "pages/messages.html", {
        "conversations": [],
        "selected_user": None,
        "selected_name": None,
        "selected_avatar": None,
        "messages": [],
    })


# --- Main View ---
@never_cache
@login_required
# MessageController
def messages_with(request, user_id):
    """Chat view between the logged-in user and other_user."""
    # ------------------------------------------------------------------
    # 0️⃣  Get the other user, profile, display-name, avatar
    # ------------------------------------------------------------------
    other_user = get_object_or_404(User, pk=user_id)

    try:
        other_profile = Profile.objects.only("name").get(user_id_fk=other_user)
        display_name = other_profile.name or other_user.email
        selected_profile = Profile.objects.get(user_id_fk=other_user)
    except Profile.DoesNotExist:
        display_name = other_user.email

    img = (
        ProfileImage.objects
        .only("image_url")
        .filter(profile_id_fk=other_profile, is_primary=1)
        .first()
    )
    avatar_url = (
        f"{settings.IMAGEKIT_URL_ENDPOINT}{img.image_url}"
        if img else settings.STATIC_URL + "img/avatar-placeholder.png"
    )

    like = Like.objects.filter(
        liker_user_id=request.user.user_id,
        liked_user_id=other_user.user_id
    ).order_by("-liked_at").first()

    liked_date = like.liked_at if like else None

    # avatar_url = img.image_url if img else settings.STATIC_URL + "img/avatar-placeholder.png"#

    # ------------------------------------------------------------------
    # 1️⃣  Find the *active* Match row involving these two users
    #      (order-agnostic, UUID fields)
    # ------------------------------------------------------------------
    match = (
        Match.objects
        .filter(is_active=1)
        .filter(
            (Q(user1_id=request.user.user_id) & Q(user2_id=other_user.user_id)) |
            (Q(user1_id=other_user.user_id) & Q(user2_id=request.user.user_id))
        )
        .first()
    )
    if not match:
        raise Http404("No active match between these users.")

    # ------------------------------------------------------------------
    # 2️⃣  POST ⇒ send a new message to Mongo
    # ------------------------------------------------------------------
    if request.method == "POST":
        body = request.POST.get("message", "").strip()
        if body:
            append_message(match, str(request.user.user_id), body)
            log_action(request.user, f"Sent message to user {user_id}", "INFO", request,
                       metadata={"message_length": len(body)})
        # after sending, redirect to GET avoids resubmission on refresh
        return redirect("messages_with", user_id=other_user.user_id)

    # ------------------------------------------------------------------
    # 3️⃣  GET ⇒ fetch message list and mark partner’s messages as read
    # ------------------------------------------------------------------
    messages = fetch_messages(match)  # list[dict] from Mongo
    mark_read(match, str(request.user.user_id))  # mark incoming as read

    # ------------------------------------------------------------------
    # 4️⃣  Render page
    # ------------------------------------------------------------------
    context = {
        "conversations": get_conversations_for(request.user),
        "selected_user": other_user,
        "selected_name": display_name,
        "selected_avatar": avatar_url,
        "messages": messages,
        "user": request.user,

        "selected_user_age": selected_profile.age,
        "selected_user_liked_date": liked_date,
    }
    return render(request, "pages/messages.html", context)


@never_cache
@login_required
# MessageController
def messages_json(request, user_id):
    """
    Return all messages, or only messages sent **after** ?after=<iso8601-stamp>.
    Used by polling JS.
    """
    other_user = get_object_or_404(User, pk=user_id)

    match = (
        Match.objects
        .filter(is_active=True)
        .filter(
            (Q(user1_id=request.user.user_id) & Q(user2_id=other_user.user_id)) |
            (Q(user1_id=other_user.user_id) & Q(user2_id=request.user.user_id))
        )
        .first()
    )
    if not match:
        return JsonResponse({"messages": []})

    since = request.GET.get("after")
    msgs = fetch_messages(match)

    if since:
        try:
            after_dt = iso8601.parse_date(since)
            msgs = [m for m in msgs
                    if iso8601.parse_date(m["sent_at"]) > after_dt]
        except iso8601.ParseError:
            pass  # ignore bad param – return full list

    # mark everything from partner as read
    mark_read(match, str(request.user.user_id))

    # send back **only** the fields the browser needs
    lite = [{
        "id": m["message_id"],
        "text": m.get("ciphertext", "[missing]"),
        "nonce": m.get("nonce", ""),
        "ts": m["sent_at"],
        "from": m["sender_user_id"],
    } for m in msgs]

    return JsonResponse({"messages": lite})


stripe.api_key = settings.STRIPE_SECRET_KEY

# ONE place that maps the slug used in URLs → the real Stripe Price IDs
PRICE_MAP = {
    "week": settings.STRIPE_PRICE_ID_WEEK,
    "month": settings.STRIPE_PRICE_ID_MONTH,
    "quarter": settings.STRIPE_PRICE_ID_QUARTER,
}


# BillingController
def _price_to_cycle(price_id: str) -> str:
    """Convert price-ID → ‘1week’ | ‘1month’ | ‘3month’ for DB column."""
    if price_id == settings.STRIPE_PRICE_ID_WEEK:
        return "1week"
    if price_id == settings.STRIPE_PRICE_ID_MONTH:
        return "1month"
    return "3month"  # quarter


# ─────────────  1)  Launch checkout  ─────────────
@login_required
# BillingController
def create_checkout_session(request, plan: str):
    """
    Called by the “Select” button.
    plan is the slug in the <a href="{% url 'stripe_checkout' plan.slug %}">.
    """
    price_id = PRICE_MAP.get(plan.lower())
    if not price_id:
        return HttpResponse("Unknown plan", status=400)

    # ➊ create a Checkout session on Stripe
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=request.user.email,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=request.build_absolute_uri(
            reverse("stripe_success")) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.build_absolute_uri(reverse("stripe_cancel")),
        metadata={
            "user_id": str(request.user.user_id),
            "plan": plan,
        },
    )

    # ➋ store a *pending* subscription row – useful even before the webhook
    _create_sub_record(
        user_uuid=request.user.user_id,
        stripe_sub_id=None,  # will be filled later
        price_id=price_id,
        stripe_session_id=session.id,
    )

    return redirect(session.url)


# ─────────────  2)  Success / cancel splash pages  ─────────────
# BillingController
@login_required
def checkout_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        print("❌ No session ID in URL.")
        return redirect("home")

    try:
        # Retrieve the session and expand subscription details
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription"]
        )

        if session["payment_status"] != "paid" or session["status"] != "complete":
            print("❌ Session not completed or not paid.")
            return redirect("home")

        user_id = session.get("metadata", {}).get("user_id")

        # Fix: Extract subscription ID safely
        subscription_obj = session.get("subscription")
        sub_id = subscription_obj["id"] if isinstance(subscription_obj, dict) else subscription_obj

        customer_id = session.get("customer")

        # Fallback in case price ID is not accessible via deprecated display_items
        price_id = None
        try:
            line_items = stripe.checkout.Session.list_line_items(session_id)
            if line_items.data:
                price_id = line_items.data[0].price.id
        except Exception as e:
            print("⚠️ Failed to fetch price ID from line_items:", e)

        if not user_id:
            print("❌ No user ID found in metadata.")
            return redirect("home")

        # Update subscription
        try:
            subscription = Subscription.objects.get(stripe_session_id=session_id)
            subscription.status = "active"
            subscription.stripe_subscription_id = sub_id
            subscription.stripe_customer_id = customer_id
            if price_id:
                subscription.stripe_price_id = price_id
            subscription.save()
        except Subscription.DoesNotExist:
            Subscription.objects.create(
                user_uuid=user_id,
                stripe_session_id=session_id,
                stripe_subscription_id=sub_id,
                stripe_customer_id=customer_id,
                stripe_price_id=price_id,
                status="active"
            )

        # Upgrade user
        try:
            user = User.objects.get(user_id=user_id)
            user.is_premium = True
            user.save(update_fields=["is_premium"])
            print("🎉 User upgraded to premium:", user.user_id)
        except User.DoesNotExist:
            print("❌ User not found:", user_id)

    except stripe.error.StripeError as e:
        print("❌ Stripe error:", e)
        return redirect("home")
    except Exception as e:
        print("🔥 Unexpected error in checkout_success:", e)
        import traceback
        traceback.print_exc()
        return redirect("home")

    log_action(request.user, "Visited Stripe success page", "INFO", request)
    return render(request, "billing/success.html")


@login_required
# BillingController
def checkout_cancel(request):
    log_action(request.user, "Visited Stripe cancel page", "WARNING", request)
    return render(request, "billing/cancel.html")


# ─────────────  3)  Stripe web-hook  ─────────────
@csrf_exempt
def stripe_webhook(request):
    print("🚀 Webhook endpoint hit!")
    try:
        payload = request.body
        sig = request.headers.get("stripe-signature", "")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            print("❌ Webhook signature verification failed:", e)
            return HttpResponse(status=400)

        event_type = event["type"]
        print("⚡ Received event type:", event_type)

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session["id"]
            print("🧾 Session object:", session)

            # 🔍 Lookup the pending subscription using session_id
            from .models import Subscription, User  # adjust if needed
            try:
                subscription = Subscription.objects.get(stripe_session_id=session_id)
            except Subscription.DoesNotExist:
                print(f"❌ No matching subscription found for session ID: {session_id}")
                return HttpResponse(status=404)

            # ✅ Update subscription with customer/subscription ID from Stripe
            subscription.status = "active"
            subscription.stripe_customer_id = session.get("customer")
            subscription.stripe_subscription_id = session.get("subscription")
            subscription.save()

            # ✅ Upgrade the user to premium
            try:
                user = User.objects.get(user_id=subscription.user_uuid)
                user.is_premium = True
                user.save(update_fields=["is_premium"])
                print("🎉 Upgraded user to premium:", user.user_id)
            except User.DoesNotExist:
                print(f"❌ User not found: {subscription.user_uuid}")

        return HttpResponse(status=200)

    except Exception as e:
        print("🔥 Webhook error:", str(e))
        import traceback
        traceback.print_exc()
        return HttpResponse(status=500)


# ─────────────  4)  Helpers  ─────────────
# BillingController
def _create_sub_record(
        user_uuid: str,
        stripe_sub_id: Optional[str],
        price_id: Optional[str],
        *,
        stripe_session_id: Optional[str] = None,
):
    user = User.objects.get(user_id=user_uuid)

    sub_json = (
        stripe.Subscription.retrieve(stripe_sub_id)
        if stripe_sub_id else None
    )

    #  ⬇️  DO NOT set "subscription_id" here — the model default will do it
    Subscription.objects.update_or_create(
        user_id_fk=user,
        defaults={
            "stripe_subscription_id": stripe_sub_id,
            "stripe_customer_id": sub_json["customer"] if sub_json else None,
            "stripe_price_id": price_id,
            "stripe_session_id": stripe_session_id,
            "price": sub_json["plan"]["amount"] / 100 if sub_json else None,
            "billing_cycle": _price_to_cycle(price_id) if price_id else None,
            "features": json.dumps({"premium": True}),
            "started_at": timezone.now(),
            "expires_at": (
                timezone.make_aware(
                    datetime.fromtimestamp(sub_json["current_period_end"])
                ) if sub_json else timezone.now()
            ),
            "auto_renew": 1,
            "status": sub_json["status"] if sub_json else "pending",
        },
    )

    # user.is_premium = True
    # user.save(update_fields=["is_premium"])


# BillingController
def _update_next_renewal(stripe_sub_id: str):
    sub_json = stripe.Subscription.retrieve(stripe_sub_id)
    try:
        db_sub = Subscription.objects.get(
            stripe_subscription_id=stripe_sub_id,
            status__in=["active", "trialing"],
        )
        db_sub.expires_at = timezone.make_aware(
            datetime.fromtimestamp(sub_json["current_period_end"])
        )
        db_sub.status = sub_json["status"]
        db_sub.save(update_fields=["expires_at", "status"])
    except Subscription.DoesNotExist:
        pass


# BillingController
def _check_status(stripe_sub_id: str):
    sub_json = stripe.Subscription.retrieve(stripe_sub_id)
    if sub_json["status"] in ("canceled", "unpaid"):
        try:
            db_sub = Subscription.objects.get(
                stripe_subscription_id=stripe_sub_id
            )
            db_sub.status = sub_json["status"]
            db_sub.save(update_fields=["status"])
            db_sub.user_id_fk.is_premium = False
            db_sub.user_id_fk.save(update_fields=["is_premium"])
        except Subscription.DoesNotExist:
            pass


@never_cache
@login_required
# BillingController
def upgrade_premium(request):
    plans = [
        {
            "slug": "week",  # make sure this is here
            "name": "1 Week",
            "price": "4.99",
            "description": "Short-term access to premium features",
        },
        {
            "slug": "month",
            "name": "1 Month",
            "price": "9.99",
            "description": "Unlock premium features for a month",
        },
        {
            "slug": "quarter",
            "name": "3 Months",
            "price": "24.99",
            "description": "Save more with a 3-month plan",
        },
    ]
    return render(request, "accounts/upgrade_premium.html", {"plans": plans})


@never_cache
@login_required
# MatchController
def browse_one_profile(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    try:
        current_profile = Profile.objects.get(user_id_fk=user_id)
        profiles = Profile.objects.exclude(profile_id=current_profile.profile_id).order_by('-last_updated')
    except Profile.DoesNotExist:
        return redirect('login')

    # Orientation-based filtering
    user_gender = current_profile.gender
    user_orientation = current_profile.sexual_orientation

    if user_gender and user_orientation:
        if user_orientation == "straight":
            profiles = profiles.filter(gender="female" if user_gender == "male" else "male")
        elif user_orientation == "gay":
            profiles = profiles.filter(gender=user_gender)
    # Skip filtering if unknown

    rated_likes = Like.objects.filter(liker_user_id=user_id)
    liked_user_ids = rated_likes.filter(like_status="liked").values_list('liked_user_id', flat=True)
    disliked_user_ids = rated_likes.filter(like_status="passed").values_list('liked_user_id', flat=True)
    all_profile_ids = profiles.values_list('user_id_fk', flat=True)
    unseen_ids = set(all_profile_ids) - set(liked_user_ids) - set(disliked_user_ids)
    remaining_disliked_ids = set(disliked_user_ids) & set(all_profile_ids)

    preferences = Preferences.objects.filter(profile_id_fk=current_profile).first()

    def fetch_pref(model, field):
        obj = model.objects.filter(preference_id_fk=preferences).first()
        return getattr(obj, field, None) if obj else None

    # Only show profiles the user has never seen before (i.e., not liked or passed)
    profiles = profiles.filter(user_id_fk__in=unseen_ids)

    # If none left, show browse_done
    if not profiles.exists():
        return render(request, 'pages/browse_done.html', {
            'preferences': preferences,
            'languages': Language.objects.all(),
            'gender': fetch_pref(PreferencesGender, 'gender_type'),
            'body_type': fetch_pref(PreferencesBodyType, 'body_type_value'),
            'education': fetch_pref(PreferencesEducation, 'education_level'),
            'religion': fetch_pref(PreferencesReligion, 'religion_type'),
            'ethnicity': fetch_pref(PreferencesEthnicity, 'ethnicity_type'),
            'politics': fetch_pref(PreferencesPolitics, 'politics_type'),
            'smoking': fetch_pref(PreferencesSmoking, 'smoking_type'),
            'drinking': fetch_pref(PreferencesDrinking, 'drinking_type'),
            'drug': fetch_pref(PreferencesDrug, 'drug_type'),
            'has_kids': fetch_pref(PreferencesHasKids, 'has_kids_type'),
            'wants_kids': fetch_pref(PreferencesWantsKids, 'wants_kids_type'),
            'zodiac': fetch_pref(PreferencesZodiac, 'zodiac_type'),
            'relationship': fetch_pref(PreferencesRelationship, 'relationship_type'),
            'language_id': fetch_pref(PreferencesLanguage, 'language_id_fk_id'),
            'body_choices': PreferencesBodyType._meta.get_field("body_type_value").choices,
            'education_choices': PreferencesEducation._meta.get_field("education_level").choices,
            'religion_choices': PreferencesReligion._meta.get_field("religion_type").choices,
            'ethnicity_choices': PreferencesEthnicity._meta.get_field("ethnicity_type").choices,
            'politics_choices': PreferencesPolitics._meta.get_field("politics_type").choices,
            'smoking_choices': PreferencesSmoking._meta.get_field("smoking_type").choices,
            'drinking_choices': PreferencesDrinking._meta.get_field("drinking_type").choices,
            'drug_choices': PreferencesDrug._meta.get_field("drug_type").choices,
            'wants_kids_choices': PreferencesWantsKids._meta.get_field("wants_kids_type").choices,
            'zodiac_choices': PreferencesZodiac._meta.get_field("zodiac_type").choices,
            'relationship_choices': PreferencesRelationship._meta.get_field("relationship_type").choices,
        })

    unseen_profiles = profiles.exclude(user_id_fk__in=liked_user_ids).exclude(user_id_fk__in=disliked_user_ids)

    profiles = unseen_profiles

    liked_profiles = Profile.objects.filter(
        user_id_fk__in=Like.objects.filter(liker_user_id=user_id, like_status="liked").values_list('liked_user_id',
                                                                                                   flat=True)
    )

    weights = {
        "height": 2, "gender": 3, "body": 1, "education": 1,
        "religion": 1, "politics": 1, "smoking": 1, "drinking": 1,
        "drug": 1, "has_kids": 1, "wants_kids": 1, "zodiac": 0.5,
        "relationship": 2.5, "language": 2,
    }

    def profile_to_vector(profile):
        gender_vec = [1 if profile.gender == 'male' else 0, 1 if profile.gender == 'female' else 0]
        age_vec = [profile.age or 0]
        tags = [
            profile.body_type, profile.education_level, profile.religion,
            profile.politics, profile.smoking, profile.drinking,
            profile.drug_use, profile.has_kids, profile.wants_kids,
            profile.zodiac_sign, profile.relationship_goals
        ]
        tag_vec = [hash(tag) % 100 for tag in tags if tag]
        return np.array(gender_vec + age_vec + tag_vec, dtype='float64')

    def compute_match_score(profile, preferences, weights):
        score = 0

        if not preferences:
            return score

        if preferences.preferred_height_min and preferences.preferred_height_max and profile.height_cm:
            if preferences.preferred_height_min <= profile.height_cm <= preferences.preferred_height_max:
                score += weights["height"]

        def match_field(pref_model, profile_value, field, weight_key):
            if not pref_model:
                return 0
            return weights.get(weight_key, 0) if getattr(pref_model, field, None) == profile_value else 0

        score += match_field(PreferencesGender.objects.filter(preference_id_fk=preferences).first(), profile.gender,
                             "gender_type", "gender")
        score += match_field(PreferencesBodyType.objects.filter(preference_id_fk=preferences).first(),
                             profile.body_type, "body_type_value", "body")
        score += match_field(PreferencesEducation.objects.filter(preference_id_fk=preferences).first(),
                             profile.education_level, "education_level", "education")
        score += match_field(PreferencesReligion.objects.filter(preference_id_fk=preferences).first(), profile.religion,
                             "religion_type", "religion")
        score += match_field(PreferencesPolitics.objects.filter(preference_id_fk=preferences).first(), profile.politics,
                             "politics_type", "politics")
        score += match_field(PreferencesSmoking.objects.filter(preference_id_fk=preferences).first(), profile.smoking,
                             "smoking_type", "smoking")
        score += match_field(PreferencesDrinking.objects.filter(preference_id_fk=preferences).first(), profile.drinking,
                             "drinking_type", "drinking")
        score += match_field(PreferencesDrug.objects.filter(preference_id_fk=preferences).first(), profile.drug_use,
                             "drug_type", "drug")
        score += match_field(PreferencesHasKids.objects.filter(preference_id_fk=preferences).first(), profile.has_kids,
                             "has_kids_type", "has_kids")
        score += match_field(PreferencesWantsKids.objects.filter(preference_id_fk=preferences).first(),
                             profile.wants_kids, "wants_kids_type", "wants_kids")
        score += match_field(PreferencesZodiac.objects.filter(preference_id_fk=preferences).first(),
                             profile.zodiac_sign, "zodiac_type", "zodiac")
        score += match_field(PreferencesRelationship.objects.filter(preference_id_fk=preferences).first(),
                             profile.relationship_goals, "relationship_type", "relationship")

        pref_lang = PreferencesLanguage.objects.filter(preference_id_fk=preferences).first()
        if pref_lang:
            user_lang_ids = profile.languages.values_list("language_id_fk_id", flat=True)
            if pref_lang.language_id_fk_id in user_lang_ids:
                score += weights["language"]

        return score

    def compute_knn_score(candidate_profile, liked_profiles, top_k=3):
        def construct_vector(profile):
            try:
                return np.array([
                    1 if profile.gender == "female" else 0,
                    profile.age or 0,
                    profile.height_cm or 0,
                    1 if profile.smoking == "yes" else 0,
                    1 if profile.drinking == "yes" else 0,
                    1 if profile.drug_use == "yes" else 0,
                    1 if profile.has_kids == "yes" else 0,
                    1 if profile.wants_kids == "want kids" else 0,
                    1 if profile.relationship_goals == "life partner" else 0,
                    1 if profile.body_type == "fit" else 0,
                    1 if profile.education_level == "undergraduate" else 0,
                    1 if profile.politics == "liberal" else 0,
                    1 if profile.religion == "agnostic" else 0,
                ])
            except:
                return None

        candidate_vec = construct_vector(candidate_profile)
        if candidate_vec is None:
            return 0

        candidate_vec = candidate_vec.reshape(1, -1)
        liked_vectors = []

        for lp in liked_profiles:
            if isinstance(lp, np.ndarray):
                vec = lp  # Already a vector, no need to reconstruct
            else:
                vec = construct_vector(lp)

            if isinstance(vec, np.ndarray) and vec.shape[0] == candidate_vec.shape[1]:
                liked_vectors.append(vec)

        liked_vectors = [construct_vector(lp) for lp in liked_profiles if construct_vector(lp) is not None]

        if not liked_vectors:
            return 0

        similarities = [
            cosine_similarity(candidate_vec, lp.reshape(1, -1))[0][0]
            for lp in liked_vectors
        ]

        top_k_similarities = sorted(similarities, reverse=True)[:top_k]
        return sum(top_k_similarities) / len(top_k_similarities)

    priority_profiles = []
    secondary_profiles = []

    for profile in profiles:
        primary_image = ProfileImage.objects.filter(profile_id_fk=profile.profile_id, is_primary=True).first()
        image_url = get_safe_profile_image_url(primary_image, is_premium=True)  # No blur needed

        score = compute_match_score(profile, preferences, weights)
        knn_score = compute_knn_score(profile, liked_profiles)
        score += knn_score * 10

        normalized_score = int((score / 19) * 100)

        entry = {
            'profile': profile,
            'image_url': image_url,
            'score': normalized_score,
            'images': [
                {
                    'url': get_safe_profile_image_url(img, True),
                    'is_primary': img.is_primary,
                }
                for img in ProfileImage.objects.filter(profile_id_fk=profile.profile_id).order_by('-uploaded_at')
            ]
        }

        if preferences and preferences.preferred_age_min and preferences.preferred_age_max:
            if preferences.preferred_age_min <= profile.age <= preferences.preferred_age_max:
                priority_profiles.append(entry)
            else:
                secondary_profiles.append(entry)
        else:
            priority_profiles.append(entry)

    priority_profiles.sort(key=lambda x: x['score'], reverse=True)
    secondary_profiles.sort(key=lambda x: x['score'], reverse=True)
    scored_profiles = priority_profiles + secondary_profiles

    index = int(request.GET.get('index', 0))
    if index >= len(scored_profiles):
        return redirect('/browse/?index=0')

    match_popup = request.session.pop('match_popup', None)
    entry = scored_profiles[index]

    context = {
        'entry': entry,
        'next_index': index + 1,
        'match_popup': match_popup,
        'preferences': preferences,
        'languages': Language.objects.all(),
        'gender': fetch_pref(PreferencesGender, 'gender_type'),
        'body_type': fetch_pref(PreferencesBodyType, 'body_type_value'),
        'education': fetch_pref(PreferencesEducation, 'education_level'),
        'religion': fetch_pref(PreferencesReligion, 'religion_type'),
        'ethnicity': fetch_pref(PreferencesEthnicity, 'ethnicity_type'),
        'politics': fetch_pref(PreferencesPolitics, 'politics_type'),
        'smoking': fetch_pref(PreferencesSmoking, 'smoking_type'),
        'drinking': fetch_pref(PreferencesDrinking, 'drinking_type'),
        'drug': fetch_pref(PreferencesDrug, 'drug_type'),
        'has_kids': fetch_pref(PreferencesHasKids, 'has_kids_type'),
        'wants_kids': fetch_pref(PreferencesWantsKids, 'wants_kids_type'),
        'zodiac': fetch_pref(PreferencesZodiac, 'zodiac_type'),
        'relationship': fetch_pref(PreferencesRelationship, 'relationship_type'),
        'language_id': fetch_pref(PreferencesLanguage, 'language_id_fk_id'),
        'body_choices': PreferencesBodyType._meta.get_field("body_type_value").choices,
        'education_choices': PreferencesEducation._meta.get_field("education_level").choices,
        'religion_choices': PreferencesReligion._meta.get_field("religion_type").choices,
        'ethnicity_choices': PreferencesEthnicity._meta.get_field("ethnicity_type").choices,
        'politics_choices': PreferencesPolitics._meta.get_field("politics_type").choices,
        'smoking_choices': PreferencesSmoking._meta.get_field("smoking_type").choices,
        'drinking_choices': PreferencesDrinking._meta.get_field("drinking_type").choices,
        'drug_choices': PreferencesDrug._meta.get_field("drug_type").choices,
        'wants_kids_choices': PreferencesWantsKids._meta.get_field("wants_kids_type").choices,
        'zodiac_choices': PreferencesZodiac._meta.get_field("zodiac_type").choices,
        'relationship_choices': PreferencesRelationship._meta.get_field("relationship_type").choices,
    }

    # Check if current user has already reported the current profile
    current_profile_user_id = entry['profile'].user_id_fk.user_id  # profile being shown
    already_reported = Report.objects.filter(
        reporter_user=request.user,
        reported_user_id=current_profile_user_id
    ).exists()

    # 🔐 Store the currently shown profile for report validation
    request.session['last_profile_id'] = entry['profile'].user_id_fk.user_id

    context['already_reported'] = already_reported
    context['profile'] = entry['profile']
    return render(request, 'pages/browse.html', context)


@login_required
# MatchController
def like_profile(request):
    liker_user_uuid = request.session.get("user_id")
    if not liker_user_uuid:
        return redirect('/login/')

    if request.method == 'POST':
        liked_user_uuid = request.POST.get("liked_user_id")

        tab_raw = request.POST.get("from_likes", "").strip()

        try:
            liker_user = User.objects.get(user_id=liker_user_uuid)
            liked_user = User.objects.get(user_id=liked_user_uuid)
        except User.DoesNotExist:
            return redirect('/browse/')

        # Update if exists, else create
        existing_like = Like.objects.filter(
            liker_user_id=liker_user,
            liked_user_id=liked_user
        ).first()

        if existing_like:
            existing_like.like_status = 'liked'
            existing_like.liked_at = timezone.now()
            existing_like.save()
        else:
            Like.objects.create(
                like_id=str(uuid.uuid4()),
                like_status='liked',
                liker_user_id=liker_user,
                liked_user_id=liked_user,
                liked_at=timezone.now()
            )

        # Check for mutual like
        mutual_like = Like.objects.filter(
            liker_user_id=liked_user,
            liked_user_id=liker_user,
            like_status='liked'
        ).exists()

        if mutual_like:
            already_matched = Match.objects.filter(
                user1_id__in=[liker_user, liked_user],
                user2_id__in=[liker_user, liked_user]
            ).exists()

            if not already_matched:
                Match.objects.create(
                    match_id=str(uuid.uuid4()),
                    user1_id=liker_user,
                    user2_id=liked_user,
                    matched_at=timezone.now(),
                    is_active=True
                )

                profile = liked_user.profile
                image = profile.profileimage_set.filter(is_primary=True).first()
                popup_data = {
                    'name': profile.name,
                    'image': f"{settings.IMAGEKIT_URL_ENDPOINT}{image.image_url}" if image and image.image_url else '/static/images/default-avatar.jpg'
                }

                print("📸 Match Popup Image URL:", popup_data['image'])

                if tab_raw in ["incoming", "outgoing"]:
                    request.session['match_popup_likes'] = popup_data
                else:
                    request.session['match_popup'] = popup_data

        # ✅ Redirect to the correct page
        if tab_raw in ["incoming", "outgoing"]:
            return redirect(f'/likes/?tab={tab_raw}')

        next_index = int(request.GET.get("index", 0)) + 1
        return redirect(f"/browse/?index={next_index}")


@login_required
# MatchController
@login_required
def save_preferences(request):
    profile = get_object_or_404(Profile, user_id_fk=request.user)

    if request.method == "POST":
        form = PreferencesForm(request.POST, instance=profile.preferences)
        if form.is_valid():
            preferences = form.save(commit=False)
            preferences.profile_id_fk = profile
            preferences.save()

            # 🛠 Nested helper function can access request directly
            def update_pref(model, field, post_key, allowed_values=None):
                val = request.POST.get(post_key)
                if not val or val == "---":
                    model.objects.filter(preference_id_fk=preferences).delete()
                else:
                    val = val.replace("'", "’")  # Normalize apostrophes
                    if allowed_values is None or val in allowed_values:
                        model.objects.update_or_create(
                            preference_id_fk=preferences, defaults={field: val}
                        )

            # ✅ Update each preference
            update_pref(PreferencesGender, 'gender_type', 'gender_type')
            update_pref(PreferencesBodyType, 'body_type_value', 'body_type_value')
            update_pref(PreferencesEducation, 'education_level', 'education_level')
            update_pref(PreferencesReligion, 'religion_type', 'religion_type')
            update_pref(PreferencesEthnicity, 'ethnicity_type', 'ethnicity_type')
            update_pref(PreferencesPolitics, 'politics_type', 'politics_type')
            update_pref(PreferencesSmoking, 'smoking_type', 'smoking_type')
            update_pref(PreferencesDrinking, 'drinking_type', 'drinking_type')
            update_pref(PreferencesDrug, 'drug_type', 'drug_type')
            update_pref(PreferencesHasKids, 'has_kids_type', 'has_kids_type')

            # ✅ ENUM-protected field
            update_pref(
                PreferencesWantsKids,
                'wants_kids_type',
                'wants_kids_type',
                allowed_values=["want kids", "don’t want kids", "open to kids"]
            )

            update_pref(PreferencesZodiac, 'zodiac_type', 'zodiac_type')
            update_pref(PreferencesRelationship, 'relationship_type', 'relationship_type')

            # ✅ Handle language separately
            lang_id = request.POST.get('language_id_fk')
            if lang_id:
                PreferencesLanguage.objects.update_or_create(
                    preference_id_fk=preferences,
                    defaults={'language_id_fk_id': lang_id}
                )

            log_action(request.user, "Updated preferences", "INFO", request)
            messages.success(request, "✅ Preferences updated successfully.")
            return redirect('browse_one')
        else:
            messages.error(request, "❌ Please correct the errors below.")
    else:
        form = PreferencesForm(instance=profile.preferences)

    return render(request, "pages/preferences_modal_form.html", {
        "form": form,
        "profile": profile,
    })


def save_preferences(request):
    profile = get_object_or_404(Profile, user_id_fk=request.user)

    if request.method == "POST":
        form = PreferencesForm(request.POST, instance=profile.preferences)
        if form.is_valid():
            preferences = form.save(commit=False)
            preferences.profile_id_fk = profile
            preferences.save()

            # 🛠 Nested helper function
            def update_pref(model, field, post_key, allowed_values=None):
                val = request.POST.get(post_key)
                if not val or val == "---":
                    model.objects.filter(preference_id_fk=preferences).delete()
                else:
                    val = val.replace("'", "’")
                    if allowed_values is None or val in allowed_values:
                        model.objects.update_or_create(
                            preference_id_fk=preferences, defaults={field: val}
                        )

            # ✅ Update each preference
            update_pref(PreferencesGender, 'gender_type', 'gender_type')
            update_pref(PreferencesBodyType, 'body_type_value', 'body_type_value')
            update_pref(PreferencesEducation, 'education_level', 'education_level')
            update_pref(PreferencesReligion, 'religion_type', 'religion_type')
            update_pref(PreferencesEthnicity, 'ethnicity_type', 'ethnicity_type')
            update_pref(PreferencesPolitics, 'politics_type', 'politics_type')
            update_pref(PreferencesSmoking, 'smoking_type', 'smoking_type')
            update_pref(PreferencesDrinking, 'drinking_type', 'drinking_type')
            update_pref(PreferencesDrug, 'drug_type', 'drug_type')
            update_pref(PreferencesHasKids, 'has_kids_type', 'has_kids_type')

            # ✅ ENUM-protected field
            update_pref(
                PreferencesWantsKids,
                'wants_kids_type',
                'wants_kids_type',
                allowed_values=["want kids", "don’t want kids", "open to kids"]
            )

            update_pref(PreferencesZodiac, 'zodiac_type', 'zodiac_type')
            update_pref(PreferencesRelationship, 'relationship_type', 'relationship_type')

            # ✅ Handle language separately
            lang_id = request.POST.get('language_id_fk')
            if lang_id:
                PreferencesLanguage.objects.update_or_create(
                    preference_id_fk=preferences,
                    defaults={'language_id_fk_id': lang_id}
                )

            # ✅ Redirect is now properly indented
            return redirect('browse_one')
        else:
            messages.error(request, "❌ Please correct the errors below.")
    else:
        form = PreferencesForm(instance=profile.preferences)

    return render(request, "pages/preferences_modal_form.html", {
        "form": form,
        "profile": profile,
    })


@login_required
# MatchController
def dislike_profile(request):
    liker_user_uuid = request.session.get("user_id")
    if not liker_user_uuid:
        return redirect('/login/')

    if request.method == 'POST':
        disliked_user_uuid = request.POST.get("disliked_user_id")
        tab_raw = request.POST.get("from_likes", "").strip()

        try:
            liker_user = User.objects.get(user_id=liker_user_uuid)
            disliked_user = User.objects.get(user_id=disliked_user_uuid)
        except User.DoesNotExist:
            return redirect('/browse/')

        # Update or create a dislike
        existing_dislike = Like.objects.filter(
            liker_user_id=liker_user,
            liked_user_id=disliked_user
        ).first()

        if existing_dislike:
            existing_dislike.like_status = 'passed'
            existing_dislike.liked_at = timezone.now()
            existing_dislike.save()
        else:
            Like.objects.create(
                like_id=str(uuid.uuid4()),
                like_status='passed',
                liker_user_id=liker_user,
                liked_user_id=disliked_user,
                liked_at=timezone.now()
            )

        # ❗ Deactivate the match
        Match.objects.filter(
            Q(user1_id=liker_user_uuid, user2_id=disliked_user_uuid) |
            Q(user1_id=disliked_user_uuid, user2_id=liker_user_uuid)
        ).update(is_active=0)

        # Decide where to redirect based on source
        if tab_raw in ["incoming", "outgoing"]:
            return redirect(f"/likes/?tab={tab_raw}")
        elif tab_raw == "messages":
            return redirect("/messages/")

        index = int(request.POST.get("index") or request.GET.get("index", 0))
        return redirect(f"/browse/?index={index}")


@login_required
def submit_report(request):
    if not has_permission(request.user, "submit_report"):
        return redirect('browse')

    if request.method == 'POST':
        reported_profile_id = request.POST.get('reported_profile_id')

        # Prevent session mismatch
        if reported_profile_id != request.session.get('last_profile_id'):
            messages.error(request, "❌ Profile mismatch. Report rejected.")
            return redirect(f'/browse/?index={request.GET.get("index", 0)}')

        form = ReportForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            details = form.cleaned_data['details']

            # Check for existing report
            existing_report = Report.objects.filter(
                reporter_user=request.user,
                reported_user_id=reported_profile_id
            ).first()

            if existing_report:
                messages.warning(request, "⚠️ You've already reported this user.")
            else:
                report = form.save(commit=False)
                report.report_id = uuid.uuid4()
                report.reporter_user = request.user
                report.reported_user_id = reported_profile_id
                report.created_at = timezone.now()
                report.save()

                log_action(
                    user=request.user,
                    action_type=f"Submitted report on user {reported_profile_id}",
                    severity="WARNING",
                    request=request,
                    target_id=reported_profile_id,
                    target_type="User",
                    metadata={"reason": reason, "details": details}
                )
                messages.success(request, "🚩 Report submitted successfully.")

                # Skip the reported profile
                Like.objects.update_or_create(
                    liker_user_id=request.user,
                    liked_user_id=User.objects.get(user_id=reported_profile_id),
                    defaults={
                        'like_status': 'passed',
                        'liked_at': timezone.now()
                    }
                )

            current_index = int(request.GET.get("index", 0))
            return redirect(f'/browse/?index={current_index + 1}')
        else:
            messages.error(request, "❌ Please correct the errors below.")

    return redirect(f'/browse/?index={request.GET.get("index", 0)}')


# Admin Reports Functionalities
@never_cache
@login_required
@user_passes_test(is_admin)
# ReportController
def admin_report_dashboard(request):
    reports = Report.objects.select_related('reporter_user').order_by('-created_at')

    # Optional filtering
    status_filter = request.GET.get('status')
    reporter_filter = request.GET.get('reporter')
    reported_user_filter = request.GET.get('reported')
    reason_filter = request.GET.get('reason')

    if status_filter:
        reports = reports.filter(status=status_filter)
    if reporter_filter:
        reports = reports.filter(reporter_user__email__icontains=reporter_filter)
    if reported_user_filter:
        reports = reports.filter(reported_user_id__icontains=reported_user_filter)
    if reason_filter:
        reports = reports.filter(reason__icontains=reason_filter)

    paginator = Paginator(reports, 10)
    page_number = request.GET.get("page")
    reports_page = paginator.get_page(page_number)

    return render(request, 'accounts/admin_report_dashboard.html', {
        'reports': reports_page,
        'status_filter': status_filter or '',
        'reporter_filter': reporter_filter or '',
        'reported_user_filter': reported_user_filter or '',
        'reason_filter': reason_filter or '',
    })


@never_cache
@login_required
@user_passes_test(is_admin)
# ReportController
def toggle_report_status(request, report_id):
    report = get_object_or_404(Report, report_id=report_id)

    if report.status == "resolved":
        action = "Unresolved"
        report.status = "pending"
        report.resolved_at = None
        report.resolved_by_user = None
    else:
        action = "Resolved"
        report.status = "resolved"
        report.resolved_at = timezone.now()
        report.resolved_by_user = request.user
    report.save()
    log_action(user=request.user, action_type=f"{action} report {report.report_id}", severity="INFO",
               request=request, target_id=report.report_id, target_type="Report")
    return redirect('admin_report_dashboard')


@never_cache
@login_required
@user_passes_test(is_admin)
@require_POST
# ReportController
def delete_report(request, report_id):
    report = get_object_or_404(Report, report_id=report_id)
    log_action(user=request.user, action_type=f"Deleted report {report.report_id}", severity="WARNING", request=request,
               target_id=report.report_id, target_type="Report")
    report.delete()
    return redirect('admin_report_dashboard')


@never_cache
@login_required
@user_passes_test(is_admin)
# AdminController
def admin_toggle_premium(request, user_id):
    user = get_object_or_404(User, user_id=user_id)
    user.is_premium = not user.is_premium
    user.save()

    status = "upgraded to Premium" if user.is_premium else "downgraded to Free"
    log_action(request.user, f"Toggled premium status for {user.email} to {user.is_premium}", severity="INFO",
               request=request, target_id=user.user_id, target_type="User")
    return redirect('admin_dashboard')


@never_cache
@login_required
@user_passes_test(is_admin)
@require_POST
# AdminController
def admin_delete_user(request, user_id):
    user = get_object_or_404(User, user_id=user_id)

    try:
        with transaction.atomic():
            # Delete related profile first
            if hasattr(user, 'profile'):
                user.profile.delete()
            user.delete()

        log_action(request.user, f"Deleted user account {user.email}", severity="WARNING",
                   request=request, target_id=user_id, target_type="User")
    except Exception as e:
        print(f"❌ Failed to delete user {user.email}: {e}")

    return redirect('admin_dashboard')