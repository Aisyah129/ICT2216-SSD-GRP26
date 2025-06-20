# authentication/views.py

from django.contrib.auth import login as auth_login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from authentication.models import User, Like, Profile, ProfileImage
from .forms import LoginForm, SignUpForm, ProfileForm
import uuid
from django.utils import timezone
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from urllib.parse import quote
from django.contrib import messages
from django.core.mail import send_mail
import random
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Content, Personalization
import os
import certifi
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
                    msg = "Invalid password"
            except User.DoesNotExist:
                msg = "User not found"
        else:
            msg = "Form not valid"

    return render(request, "accounts/login.html", {"form": form, "msg": msg})


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

            # Clear verification session
            del request.session['registration_data']
            del request.session['verification_code']

            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('user_dashboard')
        else:
            msg = "Invalid verification code."

    return render(request, "accounts/verify.html", {"msg": msg})



# USER DASHBOARD — use @login_required
@login_required
def user_dashboard(request):
    user = request.user  # automatically available
    print("✅ USER EMAIL:", user.email)

    matches = [
        {'name': 'Alex', 'age': 26, 'location': 'Singapore', 'profile_pic': {'url': 'https://via.placeholder.com/300x200'}},
        {'name': 'Jamie', 'age': 24, 'location': 'Malaysia', 'profile_pic': {'url': 'https://via.placeholder.com/300x200'}}
    ]

    return render(request, 'pages/browse.html', {
        'user': user,
        'matches': matches
    })


@login_required
def profile_view(request):
    profile = get_object_or_404(Profile, user_id_fk=request.user)

    # --------- POST: save edits ---------
    if request.method == "POST":
        # whitelist fields we actually allow to change
        editable_fields = [
            'age', 'gender', 'height_cm', 'sexual_orientation', 'pronouns',
            'body_type', 'location', 'education_level', 'occupation',
            'religion', 'ethnicity', 'politics', 'smoking', 'drinking',
            'drug_use', 'has_kids', 'wants_kids', 'zodiac_sign',
            'relationship_goals', 'hobbies', 'bio'
        ]

        for field in editable_fields:
            if field in request.POST:                          # field present?
                value = request.POST.get(field).strip()
                setattr(profile, field, value or None)        # empty → NULL

        profile.last_updated = timezone.now()
        profile.save(update_fields=editable_fields + ['last_updated'])

        messages.success(request, "Profile updated!")
        print("POST received:", request.POST)
        return redirect('profile')             # GET-redirect → read-only mode

    # --------- GET: display page ---------
    primary_image = profile.profileimage_set.filter(is_primary=True).first()
    languages     = [pl.language_id_fk.language_name
                     for pl in profile.profilelanguage_set.all()]
    pets          = [pp.pet_id_fk.pet_type
                     for pp in profile.profilepet_set.all()]

    return render(request, "pages/profile.html", {
        "profile":       profile,
        "primary_image": primary_image,
        "languages":     languages,
        "pets":          pets,
    })

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