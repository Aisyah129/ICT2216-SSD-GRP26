# authentication/views/profile_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.conf import settings
import uuid, magic, boto3
from authentication.models import Profile, ProfileImage, Language, ProfileLanguage
from authentication.utils import log_action, has_permission, get_safe_profile_image_url

MAX_IMAGES = 6

@login_required
def profile_view(request):
    profile = get_object_or_404(Profile, user_id_fk=request.user)
    if not has_permission(request.user, "edit_own_profile", profile):
        return redirect('login')

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

        profile.languages.all().delete()
        selected_lang_ids = request.POST.getlist("languages")
        for lang_id in selected_lang_ids:
            try:
                lang_obj = Language.objects.get(language_id=lang_id)
                ProfileLanguage.objects.create(profile_id_fk=profile, language_id_fk=lang_obj)
            except Language.DoesNotExist:
                continue

        log_action(request.user, "Updated profile information", "INFO", request)
        return redirect('profile')

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
        "profile": profile,
        "primary_image": primary_image_url,
        "images": all_images,
        "languages": [pl.language_id_fk.language_name for pl in profile.languages.all()],
        "all_languages": all_languages,
        "selected_language_ids": selected_language_ids,
    })

@login_required
@require_POST
def upload_profile_image(request):
    file = request.FILES.get("image")
    if not file:
        log_action(request.user, "Failed image upload - no image provided", "WARNING", request)
        return JsonResponse({"success": False, "error": "No image uploaded"}, status=400)

    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif']
    extension = file.name.split('.')[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return JsonResponse({"success": False, "error": "Invalid file extension."}, status=400)

    file_sample = file.read(2048)
    file.seek(0)
    mime_type = magic.from_buffer(file_sample, mime=True)
    if mime_type not in ['image/jpeg', 'image/png', 'image/gif']:
        return JsonResponse({"success": False, "error": "Invalid MIME type."}, status=400)

    profile = request.user.profile
    current_count = ProfileImage.objects.filter(profile_id_fk=profile).count()
    if current_count >= MAX_IMAGES:
        return JsonResponse({"success": False, "error": f"Limit of {MAX_IMAGES} images reached"}, status=400)

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
    has_primary = ProfileImage.objects.filter(profile_id_fk=profile, is_primary=True).exists()
    if want_primary or not has_primary:
        ProfileImage.objects.filter(profile_id_fk=profile).update(is_primary=False)
        primary_flag = True
    else:
        primary_flag = False

    new_image = ProfileImage.objects.create(
        image_id=str(uuid.uuid4()),
        profile_id_fk=profile,
        image_url=filename,
        is_primary=primary_flag,
        uploaded_at=timezone.now(),
    )

    log_action(request.user, "Uploaded new profile image", "INFO", request, metadata={"filename": filename})
    public_url = get_safe_profile_image_url(new_image, request.user.is_premium)
    return JsonResponse({"success": True, "image_url": public_url})

@login_required
def profile_images_json(request):
    profile = request.user.profile
    images = ProfileImage.objects.filter(profile_id_fk=profile).order_by('-uploaded_at')
    return JsonResponse([
        {
            "image_id": str(img.image_id),
            "image_url": get_safe_profile_image_url(img, request.user.is_premium),
            "is_primary": img.is_primary,
        } for img in images
    ], safe=False)

@login_required
@require_POST
def set_primary_image(request, pk):
    profile = request.user.profile
    ProfileImage.objects.filter(profile_id_fk=profile).update(is_primary=False)
    updated = ProfileImage.objects.filter(profile_id_fk=profile, pk=pk).update(is_primary=True)
    if updated:
        log_action(request.user, f"Set image {pk} as primary", "INFO", request)
    return JsonResponse({"success": bool(updated)})

@login_required
@require_http_methods(["DELETE"])
def delete_profile_image(request, pk):
    try:
        profile = request.user.profile
        image = ProfileImage.objects.get(profile_id_fk=profile, pk=pk)
        filename = image.image_url.strip("/")
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=filename)
        image.delete()
        log_action(request.user, f"Deleted profile image {pk}", "INFO", request)
        return JsonResponse({"success": True})
    except ProfileImage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Image not found"}, status=404)

def get_primary_image(profile_id):
    return ProfileImage.objects.filter(profile_id_fk=profile_id, is_primary=1).first()

def get_blurred_image_url(original_url):
    if not original_url:
        return None
    filename = original_url.split("/")[-1]
    return f"{settings.IMAGEKIT_URL_ENDPOINT}tr:bl-20/{filename}"

def get_safe_profile_image_url(image, is_premium):
    default_url = '/static/images/default-avatar.jpg'
    blurred_default_url = '/static/images/blurred-default-avatar.jpg'
    if not image:
        return default_url if is_premium else blurred_default_url
    filename = image.image_url.lstrip("/")
    return f"{settings.IMAGEKIT_URL_ENDPOINT}{filename}" if is_premium else f"{settings.IMAGEKIT_URL_ENDPOINT}tr:bl-20/{filename}"
