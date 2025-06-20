# authentication/views.py

from django.contrib.auth import login as auth_login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from authentication.models import User, Like, Profile, ProfileImage
from .forms import LoginForm, SignUpForm, ProfileForm
import uuid
import boto3
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
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

