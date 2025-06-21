from django.contrib.auth.hashers import make_password, check_password
from authentication.models import *
from .forms import LoginForm, SignUpForm
import uuid
from django.utils import timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
import logging
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)

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

    matches = []  # Placeholder for future matching logic

    return render(request, 'pages/browse.html', {
        'user': user,
        'matches': matches
    })

def admin_dashboard(request):
    users = User.objects.filter(role='user')
    return render(request, 'accounts/admin_dashboard.html', {'users': users})

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
