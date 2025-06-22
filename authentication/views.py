import json
import os
import random
from django.contrib.auth.hashers import make_password, check_password
from authentication.models import *
from .forms import LoginForm, SignUpForm
import uuid
from datetime import datetime
from typing import Optional  # ← used in a few type-hints

# ✦ Third-party libraries
import boto3
import certifi
import iso8601
import stripe
from pymongo import MongoClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, Personalization
from functools import lru_cache

# ✦ Django core
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password  
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

# ✦ Django ORM
from django.db.models import Q

# ✦ Project-local
from authentication.models import (
    Like,
    Match,
    Profile,
    ProfileImage,
    Subscription,
    User,
)
from .forms import (
    LoginForm,
    PasswordResetEmailForm,
    ProfileForm,
    SetNewPasswordForm,
    SignUpForm,
    VerificationCodeForm,
)

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
import logging
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


os.environ['SSL_CERT_FILE'] = certifi.where()

# LOGIN view using Django auth
def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            try:
                user = User.objects.get(email=email)
                if user.check_password(password):  # using AbstractBaseUser
                    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('browse' if user.role == 'user' else 'admin_dashboard')
                else:
                    msg = "Please try again."
            except User.DoesNotExist:
                msg = "Please try again."
        else:
            msg = "Please try again."

    return render(request, "accounts/login.html", {"form": form, "msg": msg})


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
            send_reset_code_email(email, code)
            return redirect('verify_reset_code')
        except User.DoesNotExist:
            msg = "Invalid email address."

    return render(request, "accounts/password_reset_request.html", {"form": form, "msg": msg})


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



def verify_reset_code(request):
    form = VerificationCodeForm(request.POST or None)
    msg = None

    if request.method == "POST" and form.is_valid():
        entered_code = form.cleaned_data['code']
        if entered_code == request.session.get('reset_code'):
            return redirect('set_new_password')
        else:
            msg = "Invalid verification code."

    return render(request, "accounts/password_reset_verify.html", {"form": form, "msg": msg})


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
            # Clear session
            del request.session['reset_email']
            del request.session['reset_code']
            messages.success(request, "Password reset successful. You can now log in.")
            return redirect('login')
        except User.DoesNotExist:
            msg = "User not found."

    return render(request, "accounts/set_new_password.html", {"form": form, "msg": msg})




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




# REGISTER: store data temporarily and send code
def register_user(request):
    form = SignUpForm(request.POST or None)
    msg = None

    if request.method == "POST" and form.is_valid():
        # Temporarily store registration data in session
        request.session['registration_data'] = {
            'email': form.cleaned_data['email'],
            'password': form.cleaned_data['password'],
            'name': form.cleaned_data['name'],
            'age': form.cleaned_data['age'],
            'gender': form.cleaned_data['gender'],
            'location': form.cleaned_data['location'],
        }

        # Generate and store verification code
        verification_code = str(random.randint(100000, 999999))
        request.session['verification_code'] = verification_code

        send_verification_email(form.cleaned_data['email'], verification_code)

        return redirect('verify_email')

    return render(request, "accounts/register.html", {"form": form, "msg": msg})


# VERIFY: confirm code, then store to DB
def verify_email(request):
    msg = None

    if request.method == "POST":
        entered_code = request.POST.get("code")
        session_code = request.session.get("verification_code")
        data = request.session.get("registration_data")

        if entered_code == session_code and data:
            # Create user and profile
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

            # Clear verification session
            del request.session['registration_data']
            del request.session['verification_code']

            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('user_dashboard')
        else:
            msg = "Invalid verification code."

    return render(request, "accounts/verify.html", {"msg": msg})


def user_dashboard(request):
    if 'user_id' not in request.session:
        return redirect('login')

# USER DASHBOARD — use @login_required
@login_required
def user_dashboard(request):
    user = request.user  # automatically available
    print("✅ USER EMAIL:", user.email)

    return render(request, 'pages/browse.html', {
        'user': user,
        'matches': matches
    })


@login_required
def profile_view(request):
    profile = get_object_or_404(Profile, user_id_fk=request.user)

    # --------- POST: save edits ---------
    if request.method == "POST":
        editable_fields = [
            'age', 'gender', 'height_cm', 'sexual_orientation', 'pronouns',
            'body_type', 'location', 'education_level', 'occupation',
            'religion', 'ethnicity', 'politics', 'smoking', 'drinking',
            'drug_use', 'has_kids', 'wants_kids', 'zodiac_sign',
            'relationship_goals', 'hobbies', 'bio'
        ]

        for field in editable_fields:
            if field in request.POST:
                value = request.POST.get(field).strip()
                setattr(profile, field, value or None)

        profile.last_updated = timezone.now()
        profile.save(update_fields=editable_fields + ['last_updated'])

        messages.success(request, "Profile updated!")
        return redirect('profile')

    # --------- GET: display page ---------
    primary_image = profile.profileimage_set.filter(is_primary=True).first()
    all_images = profile.profileimage_set.order_by('-uploaded_at')

    languages = [pl.language_id_fk.language_name for pl in profile.profilelanguage_set.all()]
    pets      = [pp.pet_id_fk.pet_type for pp in profile.profilepet_set.all()]

    return render(request, "pages/profile.html", {
        "profile":       profile,
        "primary_image": primary_image,
        "images":        all_images,      # ✅ Send to frontend
        "languages":     languages,
        "pets":          pets,
    })

MAX_IMAGES = 6          # ← change here if you ever want a different limit

# ------------------------------------------------------------------
#  Upload profile image                                   (replace)
# ------------------------------------------------------------------
@login_required
@require_POST
def upload_profile_image(request):
    """
    1. Hard-cap at MAX_IMAGES per user
    2. Always keep exactly ONE primary photo
    3. Return JSON {success:bool, error?:str, image_url?:str}
    """
    file = request.FILES.get("image")
    if not file:
        return JsonResponse(
            {"success": False, "error": "No image uploaded"}, status=400)

    profile = request.user.profile

    # ───────── 1) Reject if already at the limit ──────────
    current_count = ProfileImage.objects.filter(
        profile_id_fk=profile).count()
    if current_count >= MAX_IMAGES:
        return JsonResponse(
            {"success": False,
             "error": f"Limit of {MAX_IMAGES} images reached"},
            status=400)

    # ───────── 2) Upload to S3 ──────────
    filename = f"profile_{profile.profile_id}_{uuid.uuid4()}.{file.name.split('.')[-1]}"

    s3 = boto3.client(
        "s3",
        aws_access_key_id     = settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY,
        region_name           = settings.AWS_S3_REGION_NAME,
    )

    s3.upload_fileobj(
        file,
        settings.AWS_STORAGE_BUCKET_NAME,
        filename,
        ExtraArgs={"ContentType": file.content_type},
    )

    image_url    = f"{settings.AWS_S3_ENDPOINT}/{filename}"
    want_primary = request.POST.get("is_primary") in ("1", "true", "on")

    # ───────── 3) Guarantee ONE primary ──────────
    has_primary  = ProfileImage.objects.filter(
        profile_id_fk=profile, is_primary=1).exists()

    # • If user asks for primary OR no primary exists yet → promote new one
    if want_primary or not has_primary:
        ProfileImage.objects.filter(
            profile_id_fk=profile, is_primary=1).update(is_primary=0)
        primary_flag = 1
    else:
        primary_flag = 0

    # ───────── 4) Create DB row ──────────
    ProfileImage.objects.create(
        image_id      = str(uuid.uuid4()),
        profile_id_fk = profile,
        image_url     = image_url,
        is_primary    = primary_flag,
        uploaded_at   = timezone.now(),
    )

    return JsonResponse({"success": True, "image_url": image_url})


# 🟩 Get all profile images for this user (JSON)
@login_required
def profile_images_json(request):
    images = ProfileImage.objects.filter(profile_id_fk=request.user.profile)\
                                 .values('image_id', 'image_url', 'is_primary')
    return JsonResponse(list(images), safe=False)


# 🟩 Set selected image as primary
@login_required
@require_POST
def set_primary_image(request, pk):
    profile = request.user.profile
    ProfileImage.objects.filter(profile_id_fk=profile).update(is_primary=False)
    updated = ProfileImage.objects.filter(profile_id_fk=profile, pk=pk).update(is_primary=True)

    return JsonResponse({"success": bool(updated)})


# 🟥 Delete selected image from DB and S3
@login_required
@require_http_methods(["DELETE"])
def delete_profile_image(request, pk):
    try:
        profile = request.user.profile
        image = ProfileImage.objects.get(profile_id_fk=profile, pk=pk)

        # Extract S3 key from image URL
        bucket_prefix = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/"
        if image.image_url.startswith(bucket_prefix):
            s3_key = image.image_url.replace(bucket_prefix, "")

            # Delete from S3
            s3 = boto3.client(
                "s3",
                aws_access_key_id     = settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY,
                region_name           = settings.AWS_S3_REGION_NAME,
            )
            s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key)

        # Delete from DB
        image.delete()
        return JsonResponse({"success": True})

    except ProfileImage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Image not found"}, status=404)

# ADMIN DASHBOARD
@login_required
def admin_dashboard(request):
    users = User.objects.filter(role='user')
    return render(request, 'accounts/admin_dashboard.html', {'users': users})

def get_primary_image(profile_id):
    return ProfileImage.objects.filter(profile_id_fk=profile_id, is_primary=1).first()


def get_blurred_image_url(original_url):
    if not original_url:
        return None

    filename = original_url.split("/")[-1]

    # Compose ImageKit URL
    return f"{settings.IMAGEKIT_URL_ENDPOINT}tr:bl-20/{quote(filename)}"


@login_required
def likes_page(request):
    user = request.user
    current_user_id = user.user_id
    tab = request.GET.get('tab', 'incoming')  # Default to Likes You tab
    page_number = request.GET.get('page', 1)

    incoming_likes = []
    outgoing_likes = []
    page_obj = None

    if tab == 'incoming':
        incoming_likes_raw = Like.objects.filter(liked_user_id=current_user_id).order_by('-liked_at')

        for like in incoming_likes_raw:
            # Check if mutual like exists (i.e., the current user also liked this liker)
            if Like.objects.filter(liker_user_id=current_user_id, liked_user_id=like.liker_user.user_id).exists():
                continue  # skip mutual match

            try:
                profile = Profile.objects.get(user_id_fk=like.liker_user)
                image = get_primary_image(profile.profile_id)
                incoming_likes.append({
                    'name': profile.name if user.is_premium else None,
                    'age': profile.age if user.is_premium else None,
                    'liked_date': like.liked_at if user.is_premium else None,
                    'image_url': image.image_url if user.is_premium else get_blurred_image_url(image.image_url)
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
            'page_obj': page_obj
        })

    elif tab == 'outgoing':
        outgoing_likes_raw = Like.objects.filter(liker_user_id=current_user_id).order_by('-liked_at')

        for like in outgoing_likes_raw:
            # Check if mutual like exists (i.e., the liked user also liked this user)
            if Like.objects.filter(liker_user_id=like.liked_user.user_id, liked_user_id=current_user_id).exists():
                continue  # skip mutual match

            try:
                profile = Profile.objects.get(user_id_fk=like.liked_user)
                image = get_primary_image(profile.profile_id)
                outgoing_likes.append({
                    'name': profile.name,
                    'age': profile.age,
                    'liked_date': like.liked_at,
                    'image_url': image.image_url if image else None
                })
            except Profile.DoesNotExist:
                continue

        paginator = Paginator(outgoing_likes, 6)
        page_obj = paginator.get_page(page_number)

        return render(request, 'pages/likes.html', {
            'viewer': user,
            'active_tab': 'outgoing',
            'page_obj': page_obj,
        })


def upgrade_premium(request):
    plans = [
        {'id': 'week', 'name': '1 Week', 'price': 4.99, 'description': 'Short-term access to premium features'},
        {'id': 'month', 'name': '1 Month', 'price': 9.99, 'description': 'Unlock premium features for a month'},
        {'id': 'quarter', 'name': '3 Months', 'price': 24.99, 'description': 'Save more with a 3-month plan'},
    ]
    return render(request, 'accounts/upgrade_premium.html', {'plans': plans})

def checkout_premium(request, plan_id):
    return HttpResponse(f"Stripe checkout for plan: {plan_id}")


# --- MongoDB Connection ---
@lru_cache
def mongo():
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB]

COL = mongo().messages   # <-- Each message is its own document

def fetch_messages(match, limit=None):
    q = {"match_id": str(match.match_id)}
    cursor = COL.find(q).sort("sent_at", 1)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)

def append_message(match, sender_id, text):
    msg = {
        "match_id": str(match.match_id),
        "message_id": str(uuid.uuid4()),
        "sender_user_id": sender_id,
        "ciphertext": text,
        "sent_at": datetime.utcnow().isoformat(timespec="seconds"),
        "is_read": False,
        "encryption_meta": {
            "key_id": "default", "version": 1
        },
    }
    COL.insert_one(msg)
    return msg

def mark_read(match, reader_id):
    COL.update_many(
        {
            "match_id": str(match.match_id),
            "sender_user_id": {"$ne": reader_id},
            "is_read": False
        },
        {"$set": {"is_read": True}}
    )

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
            profile  = Profile.objects.only("name").get(user_id_fk__user_id=other_uuid)
            display  = profile.name or "Unknown"
        except Profile.DoesNotExist:
            display  = "Unknown"

        # primary image (may be None)
        img = (ProfileImage.objects
                          .only("image_url")
                          .filter(profile_id_fk=profile, is_primary=1)
                          .first())
        img_url = img.image_url if img else settings.STATIC_URL + "img/avatar-placeholder.png"

        conversations.append({
            "user_id":   other_uuid,
            "name":      display,
            "avatar":    img_url,
            "unread":    unread_map.get(str(m["match_id"]), 0),
        })

    # sort: unread first, then alpha
    conversations.sort(key=lambda c: (-c["unread"], c["name"].lower()))
    return conversations

# add near messages_with
@login_required
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
@login_required
def messages_with(request, user_id):
    """Chat view between the logged-in user and `other_user`."""
    # ------------------------------------------------------------------
    # 0️⃣  Get the other user, profile, display-name, avatar
    # ------------------------------------------------------------------
    other_user = get_object_or_404(User, pk=user_id)

    try:
        other_profile = Profile.objects.only("name").get(user_id_fk=other_user)
        display_name  = other_profile.name or other_user.email
    except Profile.DoesNotExist:
        display_name  = other_user.email

    img = (
        ProfileImage.objects
        .only("image_url")
        .filter(profile_id_fk=other_profile, is_primary=1)
        .first()
    )
    avatar_url = img.image_url if img else settings.STATIC_URL + "img/avatar-placeholder.png"

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
        # after sending, redirect to GET avoids resubmission on refresh
        return redirect("messages_with", user_id=other_user.user_id)

    # ------------------------------------------------------------------
    # 3️⃣  GET ⇒ fetch message list and mark partner’s messages as read
    # ------------------------------------------------------------------
    messages = fetch_messages(match)              # list[dict] from Mongo
    mark_read(match, str(request.user.user_id))   # mark incoming as read

    # ------------------------------------------------------------------
    # 4️⃣  Render page
    # ------------------------------------------------------------------
    context = {
        "conversations":   get_conversations_for(request.user),
        "selected_user":   other_user,
        "selected_name":   display_name,
        "selected_avatar": avatar_url,
        "messages":        messages,
        "user":            request.user,
    }
    return render(request, "pages/messages.html", context)


@login_required
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
    msgs  = fetch_messages(match)

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
        "id":    m["message_id"],
        "text":  m["ciphertext"],
        "ts":    m["sent_at"],
        "from":  m["sender_user_id"],
    } for m in msgs]

    return JsonResponse({"messages": lite})


stripe.api_key = settings.STRIPE_SECRET_KEY

# ONE place that maps the slug used in URLs → the real Stripe Price IDs
PRICE_MAP = {
    "week":    settings.STRIPE_PRICE_ID_WEEK,
    "month":   settings.STRIPE_PRICE_ID_MONTH,
    "quarter": settings.STRIPE_PRICE_ID_QUARTER,
}

def _price_to_cycle(price_id: str) -> str:
    """Convert price-ID → ‘1week’ | ‘1month’ | ‘3month’ for DB column."""
    if price_id == settings.STRIPE_PRICE_ID_WEEK:
        return "1week"
    if price_id == settings.STRIPE_PRICE_ID_MONTH:
        return "1month"
    return "3month"          # quarter

# ─────────────  1)  Launch checkout  ─────────────
@login_required
def create_checkout_session(request, plan: str):
    """
    Called by the “Select” button.
    `plan` is the slug in the <a href="{% url 'stripe_checkout' plan.slug %}">.
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
            "plan":    plan,
        },
    )

    # ➋ store a *pending* subscription row – useful even before the webhook
    _create_sub_record(
        user_uuid          = request.user.user_id,
        stripe_sub_id      = None,                 # will be filled later
        price_id           = price_id,
        stripe_session_id  = session.id,
    )

    return redirect(session.url)


# ─────────────  2)  Success / cancel splash pages  ─────────────
@login_required
def checkout_success(request):
    messages.success(request, "🎉 Thanks! Your Premium is now active.")
    return render(request, "billing/success.html")


@login_required
def checkout_cancel(request):
    messages.warning(request, "Payment cancelled.")
    return render(request, "billing/cancel.html")


# ─────────────  3)  Stripe web-hook  ─────────────
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig     = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    typ = event["type"]

    # 1️⃣ Checkout finished
    if typ == "checkout.session.completed":
        session   = event["data"]["object"]
        sub_id    = session["subscription"]           # the real sub ID
        user_id   = session["metadata"]["user_id"]
        price_id  = session["display_items"][0]["price"]["id"] \
                    if session.get("display_items") else None
        _create_sub_record(
            user_uuid         = user_id,
            stripe_sub_id     = sub_id,
            price_id          = price_id,
            stripe_session_id = session["id"],
        )

    # 2️⃣ Recurring invoice paid (renewal)
    if typ == "invoice.paid":
        _update_next_renewal(event["data"]["object"]["subscription"])

    # 3️⃣ Payment failed / subscription cancelled / downgraded
    if typ in ("invoice.payment_failed", "customer.subscription.updated"):
        _check_status(event["data"]["object"]["id"])

    return HttpResponse(status=200)


# ─────────────  4)  Helpers  ─────────────
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
            "stripe_customer_id":     sub_json["customer"] if sub_json else None,
            "stripe_price_id":        price_id,
            "stripe_session_id":      stripe_session_id,
            "price":       sub_json["plan"]["amount"] / 100 if sub_json else None,
            "billing_cycle": _price_to_cycle(price_id) if price_id else None,
            "features":    json.dumps({"premium": True}),
            "started_at":  timezone.now(),
            "expires_at": (
                timezone.make_aware(
                    datetime.fromtimestamp(sub_json["current_period_end"])
                ) if sub_json else timezone.now()
            ),
            "auto_renew": 1,
            "status":     sub_json["status"] if sub_json else "pending",
        },
    )

    user.is_premium = True
    user.save(update_fields=["is_premium"])


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

def upgrade_premium(request):
    plans = [
        {
            "slug": "week",   # make sure this is here
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


def browse_one_profile(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    # Fetch current user's profile to exclude from feed
    try:
        current_profile = Profile.objects.get(user_id_fk=user_id)
        profiles = Profile.objects.exclude(profile_id=current_profile.profile_id).order_by('-last_updated')
    except Profile.DoesNotExist:
        return redirect('login')

    # ✨ Orientation-based gender filtering
    user_gender = current_profile.gender
    user_orientation = current_profile.sexual_orientation

    # Apply gender filter based on sexual orientation
    if user_orientation == "straight":
        if user_gender == "male":
            profiles = profiles.filter(gender="female")
        elif user_gender == "female":
            profiles = profiles.filter(gender="male")
    elif user_orientation == "gay":
        if user_gender == "male":
            profiles = profiles.filter(gender="male")
        elif user_gender == "female":
            profiles = profiles.filter(gender="female")
    elif user_orientation == "bisexual":
        pass  # bisexual users can see all genders, so no filter needed
    else:
        profiles = profiles.none()  # fallback for undefined orientations

    # 🧠 STEP: Filter profiles based on like/dislike history
    rated_likes = Like.objects.filter(liker_user_id=user_id)
    liked_user_ids = rated_likes.filter(like_status="liked").values_list('liked_user_id', flat=True)
    disliked_user_ids = rated_likes.filter(like_status="passed").values_list('liked_user_id', flat=True)

    # Get all available profile user IDs (excluding current user)
    all_profile_ids = profiles.values_list('user_id_fk', flat=True)

    # Determine unseen and remaining disliked IDs
    unseen_ids = set(all_profile_ids) - set(liked_user_ids) - set(disliked_user_ids)
    remaining_disliked_ids = set(disliked_user_ids) & set(all_profile_ids)

    print("📉 unseen_ids:", len(unseen_ids))
    print("📉 remaining_disliked_ids:", len(remaining_disliked_ids))

    preferences = Preferences.objects.filter(profile_id_fk=current_profile).first()

    def fetch_pref(model, field):
        obj = model.objects.filter(preference_id_fk=preferences).first()
        return getattr(obj, field, None) if obj else None

    # 👀 If all profiles have been rated and fewer than 5 disliked remain, show browse_done
    if len(unseen_ids) == 0:
        if len(remaining_disliked_ids) < 5:
            print("🔚 No profiles left and fewer than 5 disliked to reuse.")
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
        else:
            print("🔁 No unseen profiles, falling back to disliked.")
            profiles = profiles.filter(user_id_fk__in=remaining_disliked_ids)
    else:
        profiles = profiles.filter(user_id_fk__in=unseen_ids)



    # Prioritize unseen profiles
    unseen_profiles = profiles.exclude(user_id_fk__in=liked_user_ids).exclude(user_id_fk__in=disliked_user_ids)

    if unseen_profiles.exists():
        profiles = unseen_profiles
    else:
        # Only fallback to disliked if 5 or more are available
        profiles = profiles.filter(user_id_fk__in=remaining_disliked_ids)


    # 🔁 Retrieve profiles the user has previously liked
    liked_profiles = Profile.objects.filter(
        user_id_fk__in=Like.objects.filter(liker_user_id=user_id, like_status="liked").values_list('liked_user_id', flat=True)
    )


    # 🎯 Define scoring weights
    weights = {
        "height": 2, "gender": 3, "body": 1, "education": 1,
        "religion": 1, "politics": 1, "smoking": 1, "drinking": 1,
        "drug": 1, "has_kids": 1, "wants_kids": 1, "zodiac": 0.5,
        "relationship": 2.5, "language": 2,
    }

    preferences = Preferences.objects.filter(profile_id_fk=current_profile).first()

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
            return score  # no preferences to match, return score 0 

        if preferences.preferred_height_min and preferences.preferred_height_max and profile.height_cm:
            if preferences.preferred_height_min <= profile.height_cm <= preferences.preferred_height_max:
                score += weights["height"]

        def match_field(pref_model, profile_value, field, weight_key):
            if not pref_model:
                return 0
            return weights.get(weight_key, 0) if getattr(pref_model, field, None) == profile_value else 0


        score += match_field(PreferencesGender.objects.filter(preference_id_fk=preferences).first(), profile.gender, "gender_type", "gender")
        score += match_field(PreferencesBodyType.objects.filter(preference_id_fk=preferences).first(), profile.body_type, "body_type_value", "body")
        score += match_field(PreferencesEducation.objects.filter(preference_id_fk=preferences).first(), profile.education_level, "education_level", "education")
        score += match_field(PreferencesReligion.objects.filter(preference_id_fk=preferences).first(), profile.religion, "religion_type", "religion")
        score += match_field(PreferencesPolitics.objects.filter(preference_id_fk=preferences).first(), profile.politics, "politics_type", "politics")
        score += match_field(PreferencesSmoking.objects.filter(preference_id_fk=preferences).first(), profile.smoking, "smoking_type", "smoking")
        score += match_field(PreferencesDrinking.objects.filter(preference_id_fk=preferences).first(), profile.drinking, "drinking_type", "drinking")
        score += match_field(PreferencesDrug.objects.filter(preference_id_fk=preferences).first(), profile.drug_use, "drug_type", "drug")
        score += match_field(PreferencesHasKids.objects.filter(preference_id_fk=preferences).first(), profile.has_kids, "has_kids_type", "has_kids")
        score += match_field(PreferencesWantsKids.objects.filter(preference_id_fk=preferences).first(), profile.wants_kids, "wants_kids_type", "wants_kids")
        score += match_field(PreferencesZodiac.objects.filter(preference_id_fk=preferences).first(), profile.zodiac_sign, "zodiac_type", "zodiac")
        score += match_field(PreferencesRelationship.objects.filter(preference_id_fk=preferences).first(), profile.relationship_goals, "relationship_type", "relationship")

        pref_lang = PreferencesLanguage.objects.filter(preference_id_fk=preferences).first()
        if pref_lang:
            user_lang_ids = profile.languages.values_list("language_id_fk_id", flat=True)
            if pref_lang.language_id_fk_id in user_lang_ids:
                score += weights["language"]


        return score
    
    # 💡 Build vectors for liked profiles
    liked_vectors = [profile_to_vector(lp) for lp in liked_profiles]

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
            except Exception as e:
                print(f"❌ Vector construction failed: {e}, input was: {profile}")
                return None  # avoid converting to ndarray again


        candidate_vec = construct_vector(candidate_profile)
        if candidate_vec is None:
            return 0  # fallback

        candidate_vec = candidate_vec.reshape(1, -1)
        liked_vectors = []

        for lp in liked_profiles:
            if isinstance(lp, np.ndarray):
                vec = lp  # Already a vector, no need to reconstruct
            else:
                vec = construct_vector(lp)

            if isinstance(vec, np.ndarray) and vec.shape[0] == candidate_vec.shape[1]:
                liked_vectors.append(vec)


        if not liked_vectors:
            return 0  # no comparison possible

        # Cosine similarity calculation
        similarities = [
            cosine_similarity(candidate_vec, lp.reshape(1, -1))[0][0]
            for lp in liked_vectors
        ]

        # Sort and average top-k
        top_k_similarities = sorted(similarities, reverse=True)[:top_k]
        knn_score = sum(top_k_similarities) / len(top_k_similarities)

        return knn_score


    priority_profiles = []
    secondary_profiles = []

    for profile in profiles:
        images = ProfileImage.objects.filter(profile_id_fk=profile.profile_id)
        # score = compute_match_score(profile, preferences, weights)

        score = compute_match_score(profile, preferences, weights)
        knn_score = compute_knn_score(profile, liked_vectors)

        score += knn_score * 10  # You can tune this multiplier

        normalized_score = int((score / 19) * 100)

        # 🎯 If age preference is set, split by age match
        if preferences and preferences.preferred_age_min and preferences.preferred_age_max:
            if preferences.preferred_age_min <= profile.age <= preferences.preferred_age_max:
                priority_profiles.append({'profile': profile, 'images': images, 'score': normalized_score})
            else:
                secondary_profiles.append({'profile': profile, 'images': images, 'score': normalized_score})
        else:
            # If no age preference, treat everyone as priority
            priority_profiles.append({'profile': profile, 'images': images, 'score': normalized_score})

    # Sort both groups by weighted score
    priority_profiles.sort(key=lambda x: x['score'], reverse=True)
    secondary_profiles.sort(key=lambda x: x['score'], reverse=True)

    # Combine final feed
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
    }

    def fetch_pref(model, field):
        obj = model.objects.filter(preference_id_fk=preferences).first()
        return getattr(obj, field, None) if obj else None

    context.update({
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

    return render(request, 'pages/browse.html', context)

def like_profile(request):
    liker_user_uuid = request.session.get("user_id")
    if not liker_user_uuid:
        return redirect('/login/')

    if request.method == 'POST':
        liked_user_uuid = request.POST.get("liked_user_id")

        try:
            liker_user = User.objects.get(user_id=liker_user_uuid)
            liked_user = User.objects.get(user_id=liked_user_uuid)
        except User.DoesNotExist:
            return redirect('/browse/')

        existing_like = Like.objects.filter(
            liker_user_id=liker_user,
            liked_user_id=liked_user
        ).exists()

        if not existing_like:
            Like.objects.create(
                like_id=str(uuid.uuid4()),
                like_status='liked',
                liker_user_id=liker_user,
                liked_user_id=liked_user,
                liked_at=timezone.now()
            )

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
                request.session['match_popup'] = {
                    'name': profile.name,
                    'image': image.image_url if image else ""
                }

        index = int(request.GET.get("index", 0)) + 1
        return redirect(f"/browse/?index={index}")

def save_preferences(request):
    if request.method == 'POST':
        if 'user_id' not in request.session:
            return redirect('login')

        user_id = request.session['user_id']
        profile = get_object_or_404(Profile, user_id_fk=user_id)

        preferences, _ = Preferences.objects.update_or_create(
            profile_id_fk=profile,
            defaults={
                'preferred_age_min': request.POST.get('preferred_age_min')or None,
                'preferred_age_max': request.POST.get('preferred_age_max')or None,
                'preferred_distance_km': request.POST.get('preferred_distance_km')or None,
                'preferred_height_min': request.POST.get('preferred_height_min') or None,
                'preferred_height_max': request.POST.get('preferred_height_max') or None,
                'last_updated': timezone.now()
            }
        )

        def update_pref(model, field, post_key):
            val = request.POST.get(post_key)
            if val:
                model.objects.update_or_create(preference_id_fk=preferences, defaults={field: val})

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
        update_pref(PreferencesWantsKids, 'wants_kids_type', 'wants_kids_type')
        update_pref(PreferencesZodiac, 'zodiac_type', 'zodiac_type')
        update_pref(PreferencesRelationship, 'relationship_type', 'relationship_type')

        lang_id = request.POST.get('language_id_fk')
        if lang_id:
            PreferencesLanguage.objects.update_or_create(preference_id_fk=preferences, defaults={
                'language_id_fk_id': lang_id
            })

        return redirect('browse_one')

def dislike_profile(request):
    liker_user_uuid = request.session.get("user_id")
    if not liker_user_uuid:
        return redirect('/login/')

    if request.method == 'POST':
        disliked_user_uuid = request.POST.get("disliked_user_id")

        try:
            liker_user = User.objects.get(user_id=liker_user_uuid)
            disliked_user = User.objects.get(user_id=disliked_user_uuid)
        except User.DoesNotExist:
            return redirect('/browse/')

        existing_dislike = Like.objects.filter(
            liker_user_id=liker_user,
            liked_user_id=disliked_user
        ).exists()

        if not existing_dislike:
            Like.objects.create(
                like_id=str(uuid.uuid4()),
                like_status='passed',
                liker_user_id=liker_user,
                liked_user_id=disliked_user,
                liked_at=timezone.now()
            )

        index = int(request.POST.get("index") or request.GET.get("index", 0))
        return redirect(f"/browse/?index={index}")
