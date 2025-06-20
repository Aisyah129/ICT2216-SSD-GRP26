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


# REGISTER view with UUID user_id
def register_user(request):
    form = SignUpForm(request.POST or None)
    msg = None

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data['email']
            raw_password = form.cleaned_data['password']

            user = User.objects.create_user(
                user_id=str(uuid.uuid4()),  # manually assign UUID
                email=email,
                password=raw_password,
                role='user',
                is_premium=False,
                created_at=timezone.now()
            )

            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('user_dashboard')
        else:
            msg = "Form not valid"

    return render(request, "accounts/register.html", {"form": form, "msg": msg})


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


def likes_page(request):
    if 'user_id' not in request.session:
        return redirect('login')

    current_user_id = request.session['user_id']
    user = User.objects.get(user_id=current_user_id)
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

