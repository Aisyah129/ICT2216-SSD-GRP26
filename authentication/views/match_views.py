# authentication/views/match_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.db.models import Q
from django.conf import settings
import uuid
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from authentication.models import *
from authentication.utils import log_action, has_permission, get_safe_profile_image_url

@never_cache
@login_required
def browse_one_profile(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    try:
        current_profile = Profile.objects.get(user_id_fk=user_id)
        profiles = Profile.objects.exclude(profile_id=current_profile.profile_id).order_by('-last_updated')
    except Profile.DoesNotExist:
        return redirect('login')

    user_gender = current_profile.gender
    user_orientation = current_profile.sexual_orientation

    if user_gender and user_orientation:
        if user_orientation == "straight":
            profiles = profiles.filter(gender="female" if user_gender == "male" else "male")
        elif user_orientation == "gay":
            profiles = profiles.filter(gender=user_gender)

    rated_likes = Like.objects.filter(liker_user_id=user_id)
    liked_user_ids = rated_likes.filter(like_status="liked").values_list('liked_user_id', flat=True)
    disliked_user_ids = rated_likes.filter(like_status="passed").values_list('liked_user_id', flat=True)
    all_profile_ids = profiles.values_list('user_id_fk', flat=True)
    unseen_ids = set(all_profile_ids) - set(liked_user_ids) - set(disliked_user_ids)
    profiles = profiles.filter(user_id_fk__in=unseen_ids)

    if not profiles.exists():
        return render(request, 'pages/browse_done.html')

    preferences = Preferences.objects.filter(profile_id_fk=current_profile).first()
    liked_profiles = Profile.objects.filter(user_id_fk__in=liked_user_ids)

    def compute_match_score(profile):
        score = 0
        if preferences and preferences.preferred_height_min and preferences.preferred_height_max and profile.height_cm:
            if preferences.preferred_height_min <= profile.height_cm <= preferences.preferred_height_max:
                score += 2
        return score

    def compute_knn_score(candidate_profile):
        def to_vec(profile):
            try:
                return np.array([
                    1 if profile.gender == "female" else 0,
                    profile.age or 0,
                    profile.height_cm or 0,
                    1 if profile.smoking == "yes" else 0,
                    1 if profile.drinking == "yes" else 0,
                    1 if profile.drug_use == "yes" else 0
                ])
            except:
                return None

        candidate_vec = to_vec(candidate_profile)
        if candidate_vec is None:
            return 0
        liked_vecs = [to_vec(p) for p in liked_profiles if to_vec(p) is not None]
        if not liked_vecs:
            return 0
        similarities = [cosine_similarity(candidate_vec.reshape(1, -1), vec.reshape(1, -1))[0][0] for vec in liked_vecs]
        return sum(similarities) / len(similarities)

    scored_profiles = []
    for profile in profiles:
        image = ProfileImage.objects.filter(profile_id_fk=profile, is_primary=True).first()
        image_url = get_safe_profile_image_url(image, is_premium=True)
        match_score = compute_match_score(profile)
        knn_score = compute_knn_score(profile)
        total_score = match_score + knn_score * 10
        scored_profiles.append({
            "profile": profile,
            "score": total_score,
            "image_url": image_url
        })

    scored_profiles.sort(key=lambda x: x['score'], reverse=True)

    index = int(request.GET.get('index', 0))
    if index >= len(scored_profiles):
        return redirect('/browse/?index=0')

    match_popup = request.session.pop('match_popup', None)

    return render(request, 'pages/browse.html', {
        'entry': scored_profiles[index],
        'next_index': index + 1,
        'match_popup': match_popup
    })

@login_required
def like_profile(request):
    user_id = request.session.get("user_id")
    if not user_id or request.method != 'POST':
        return redirect('/login/')

    liked_user_id = request.POST.get("liked_user_id")
    tab_raw = request.POST.get("from_likes", "").strip()

    liker = get_object_or_404(User, user_id=user_id)
    liked = get_object_or_404(User, user_id=liked_user_id)

    like, created = Like.objects.update_or_create(
        liker_user_id=liker,
        liked_user_id=liked,
        defaults={"like_status": "liked", "liked_at": timezone.now()}
    )

    if Like.objects.filter(liker_user_id=liked, liked_user_id=liker, like_status='liked').exists():
        if not Match.objects.filter(user1_id__in=[liker, liked], user2_id__in=[liker, liked]).exists():
            Match.objects.create(
                match_id=str(uuid.uuid4()),
                user1_id=liker,
                user2_id=liked,
                matched_at=timezone.now(),
                is_active=True
            )
            profile = liked.profile
            image = profile.profileimage_set.filter(is_primary=True).first()
            popup_data = {
                'name': profile.name,
                'image': get_safe_profile_image_url(image, True) if image else '/static/images/default-avatar.jpg'
            }
            if tab_raw in ["incoming", "outgoing"]:
                request.session['match_popup_likes'] = popup_data
            else:
                request.session['match_popup'] = popup_data

    if tab_raw in ["incoming", "outgoing"]:
        return redirect(f'/likes/?tab={tab_raw}')

    next_index = int(request.GET.get("index", 0)) + 1
    return redirect(f"/browse/?index={next_index}")

@login_required
def dislike_profile(request):
    user_id = request.session.get("user_id")
    if not user_id or request.method != 'POST':
        return redirect('/login/')

    disliked_user_id = request.POST.get("disliked_user_id")
    tab_raw = request.POST.get("from_likes", "").strip()

    disliker = get_object_or_404(User, user_id=user_id)
    disliked = get_object_or_404(User, user_id=disliked_user_id)

    Like.objects.update_or_create(
        liker_user_id=disliker,
        liked_user_id=disliked,
        defaults={"like_status": "passed", "liked_at": timezone.now()}
    )

    Match.objects.filter(
        Q(user1_id=disliker.user_id, user2_id=disliked.user_id) |
        Q(user1_id=disliked.user_id, user2_id=disliker.user_id)
    ).update(is_active=0)

    if tab_raw in ["incoming", "outgoing"]:
        return redirect(f"/likes/?tab={tab_raw}")
    elif tab_raw == "messages":
        return redirect("/messages/")

    index = int(request.POST.get("index") or request.GET.get("index", 0))
    return redirect(f"/browse/?index={index}")

@login_required
def save_preferences(request):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        profile = get_object_or_404(Profile, user_id_fk=user_id)

        preferences, _ = Preferences.objects.update_or_create(
            profile_id_fk=profile,
            defaults={
                'preferred_age_min': request.POST.get('preferred_age_min') or None,
                'preferred_age_max': request.POST.get('preferred_age_max') or None,
                'preferred_distance_km': request.POST.get('preferred_distance_km') or None,
                'preferred_height_min': request.POST.get('preferred_height_min') or None,
                'preferred_height_max': request.POST.get('preferred_height_max') or None,
                'last_updated': timezone.now()
            }
        )

        def update_pref(model, field, post_key):
            val = request.POST.get(post_key)
            if not val or val == "---":
                model.objects.filter(preference_id_fk=preferences).delete()
            else:
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