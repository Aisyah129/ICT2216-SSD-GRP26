# authentication/models.py

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email must be set')
        email = self.normalize_email(email)

        role = extra_fields.pop('role', 'user')
        extra_fields.pop('created_at', None)

        user = self.model(
            user_id=str(uuid.uuid4()),
            email=email,
            role=role,
            is_active=True,
            is_staff=(extra_fields.get('role') == 'admin'),
            is_superuser=(extra_fields.get('role') == 'admin'),
            created_at=timezone.now(),
            **extra_fields
        )
        user.set_password(password)           # hashes and stores into password field
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    # --- Core IDs ----------------------------------------------------
    user_id = models.CharField(max_length=36, primary_key=True)

    # --- Credentials -------------------------------------------------
    email    = models.EmailField(unique=True)

    # Map Django's `password` field to the *existing* password_hash column
    password = models.CharField(max_length=128, db_column='password_hash')

    # --- Extra business fields --------------------------------------
    role        = models.CharField(max_length=10, default='user')
    is_premium  = models.BooleanField(default=False)
    created_at  = models.DateTimeField(default=timezone.now)

    # --- Django-required flags --------------------------------------
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)   # can access admin
    # `is_superuser` comes from PermissionsMixin

    # --- Config ------------------------------------------------------
    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []             # e.g. add 'role' if you want

    objects = CustomUserManager()

    class Meta:
        db_table = 'User'
        managed  = False              # keep using existing table

    def __str__(self):
        return self.email


class Language(models.Model):
    language_id = models.AutoField(primary_key=True)
    language_name = models.CharField(unique=True, max_length=10)

    class Meta:
        managed = False
        db_table = 'Language'

class Pet(models.Model):
    pet_id = models.AutoField(primary_key=True)
    pet_type = models.CharField(unique=True, max_length=7)

    class Meta:
        managed = False
        db_table = 'Pet'

class Profile(models.Model):
    profile_id = models.CharField(primary_key=True, max_length=36)
    user_id_fk = models.OneToOneField('User', models.DO_NOTHING, db_column='user_id_fk')
    name = models.CharField(max_length=255)
    bio = models.TextField(blank=True, null=True)
    age = models.IntegerField()
    gender = models.CharField(max_length=6)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField()
    sexual_orientation = models.CharField(max_length=8, blank=True, null=True)
    pronouns = models.CharField(max_length=9, blank=True, null=True)
    height_cm = models.IntegerField(blank=True, null=True)
    body_type = models.CharField(max_length=14, blank=True, null=True)
    education_level = models.CharField(max_length=16, blank=True, null=True)
    occupation = models.CharField(max_length=255, blank=True, null=True)
    religion = models.CharField(max_length=9, blank=True, null=True)
    ethnicity = models.CharField(max_length=14, blank=True, null=True)
    politics = models.CharField(max_length=13, blank=True, null=True)
    smoking = models.CharField(max_length=9, blank=True, null=True)
    drinking = models.CharField(max_length=9, blank=True, null=True)
    drug_use = models.CharField(max_length=9, blank=True, null=True)
    has_kids = models.IntegerField(blank=True, null=True)
    wants_kids = models.CharField(max_length=15, blank=True, null=True)
    zodiac_sign = models.CharField(max_length=11, blank=True, null=True)
    hobbies = models.TextField(blank=True, null=True)
    last_updated = models.DateTimeField()
    relationship_goals = models.CharField(max_length=23, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Profile'

    def __str__(self):
        return self.name


class Like(models.Model):
    like_id = models.CharField(max_length=36, primary_key=True)
    like_status = models.CharField(max_length=20)
    liker_user = models.ForeignKey(User, db_column='liker_user_id', on_delete=models.DO_NOTHING, related_name='likes_sent')
    liked_user = models.ForeignKey(User, db_column='liked_user_id', on_delete=models.DO_NOTHING, related_name='likes_received')
    liked_at = models.DateTimeField()

    class Meta:
        db_table = 'Like'
        managed = False

    def __str__(self):
        return f"{self.liker_user} → {self.liked_user} ({self.like_status})"


class ProfileImage(models.Model):
    image_id = models.CharField(primary_key=True, max_length=36)
    profile_id_fk = models.ForeignKey(Profile, models.DO_NOTHING, db_column='profile_id_fk')
    image_url = models.TextField()
    is_primary = models.IntegerField(blank=True, null=True)  # 1 for True, 0 for False
    uploaded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'ProfileImage'

    def __str__(self):
        return f"{self.profile_id_fk_id} - {self.image_url}"

class Profilelanguage(models.Model):
    profile_language_id = models.AutoField(primary_key=True)
    language_id_fk = models.ForeignKey(Language, models.DO_NOTHING, db_column='language_id_fk')
    profile_id_fk = models.ForeignKey(Profile, models.DO_NOTHING, db_column='profile_id_fk')

    class Meta:
        managed = False
        db_table = 'ProfileLanguage'
        unique_together = (('profile_id_fk', 'language_id_fk'),)


class Profilepet(models.Model):
    profile_pet_id = models.AutoField(primary_key=True)
    profile_id_fk = models.ForeignKey(Profile, models.DO_NOTHING, db_column='profile_id_fk')
    pet_id_fk = models.ForeignKey(Pet, models.DO_NOTHING, db_column='pet_id_fk')

    class Meta:
        managed = False
        db_table = 'ProfilePet'
        unique_together = (('profile_id_fk', 'pet_id_fk'),)

class Match(models.Model):
    match_id = models.CharField(primary_key=True, max_length=36)
    user1 = models.ForeignKey('User', models.DO_NOTHING)
    user2 = models.ForeignKey('User', models.DO_NOTHING, related_name='match_user2_set')
    matched_at = models.DateTimeField()
    is_active = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Match'

class Subscription(models.Model):
    subscription_id = models.CharField(
        max_length=36, primary_key=True, db_column="subscription_id"
    )
    user_id_fk = models.OneToOneField(
        "User", models.DO_NOTHING, db_column="user_id_fk"
    )

    stripe_subscription_id = models.CharField(
        max_length=255, null=True, blank=True, db_column="stripe_subscription_id"
    )
    stripe_customer_id = models.CharField(
        max_length=255, null=True, blank=True, db_column="stripe_customer_id"
    )
    stripe_price_id = models.CharField(
        max_length=100, null=True, blank=True, db_column="stripe_price_id"
    )
    stripe_session_id = models.CharField(
        max_length=255, null=True, blank=True, db_column="stripe_session_id"
    )
    
    price          = models.FloatField(null=True, blank=True)
    features       = models.JSONField(null=True, blank=True)
    billing_cycle  = models.CharField(max_length=6)          # 1week/1month/3month
    started_at     = models.DateTimeField()
    expires_at     = models.DateTimeField()
    auto_renew     = models.IntegerField(null=True, blank=True)
    status         = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed  = False           # keep using the pre-built table
        db_table = "Subscription"

class ProfileImage(models.Model):
    image_id = models.CharField(primary_key=True, max_length=36)
    profile_id_fk = models.ForeignKey(Profile, on_delete=models.CASCADE, db_column='profile_id_fk')
    image_url = models.TextField()
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'ProfileImage'

class Like(models.Model):
    like_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    like_status = models.CharField(max_length=10, choices=[('liked', 'Liked')])
    liked_user_id = models.ForeignKey(User, db_column='liked_user_id', on_delete=models.CASCADE,
        related_name='likes_given')
    liker_user_id = models.ForeignKey(User, db_column='liker_user_id', on_delete=models.CASCADE,
        related_name='likes_received')
    liked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'Like'
        unique_together = ('liker_user_id', 'liked_user_id')  # prevent duplicate likes

    def __str__(self):
        return f"{self.liker_user_id} liked {self.liked_user_id}"

class Match(models.Model):
    match_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user1_id = models.ForeignKey('User', db_column='user1_id', on_delete=models.CASCADE, related_name='matches_as_user1')
    user2_id = models.ForeignKey('User', db_column='user2_id', on_delete=models.CASCADE, related_name='matches_as_user2')
    matched_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'Match'
        unique_together = (('user1_id', 'user2_id'),)

    def __str__(self):
        return f"Match: {self.user1_id} ❤ {self.user2_id}"


class Language(models.Model):
    language_id = models.AutoField(primary_key=True)
    language_name = models.CharField(
        max_length=20,
        choices=[
            ('english', 'English'), ('chinese', 'Chinese'), ('malay', 'Malay'), ('tamil', 'Tamil'),
            ('hindi', 'Hindi'), ('japanese', 'Japanese'), ('korean', 'Korean'), ('thai', 'Thai'),
            ('vietnamese', 'Vietnamese'), ('spanish', 'Spanish'), ('french', 'French'), ('german', 'German'),
            ('russian', 'Russian'), ('arabic', 'Arabic'), ('portuguese', 'Portuguese'), ('bengali', 'Bengali'),
            ('urdu', 'Urdu'), ('others', 'Others')
        ]
    )

    class Meta:
        db_table = 'Language'

class ProfileLanguage(models.Model):
    profile_id_fk = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        db_column='profile_id_fk',
        related_name='languages'
    )
    language_id_fk = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        db_column='language_id_fk'
    )

    class Meta:
        db_table = 'ProfileLanguage'

class Preferences(models.Model):
    preference_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile_id_fk = models.OneToOneField('Profile', models.CASCADE, db_column='profile_id_fk')
    preferred_age_min = models.IntegerField()
    preferred_age_max = models.IntegerField()
    preferred_distance_km = models.IntegerField()
    preferred_height_min = models.IntegerField(null=True, blank=True)
    preferred_height_max = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Preferences'

class PreferencesGender(models.Model):
    preferences_gender_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    gender_type = models.CharField(max_length=6, choices=[('male', 'Male'), ('female', 'Female')])

    class Meta:
        db_table = 'PreferencesGender'

class PreferencesBodyType(models.Model):
    preferences_bodytype_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    body_type_value = models.CharField(max_length=20, choices=[
        ('thin', 'Thin'), ('skinny', 'Skinny'), ('fit', 'Fit'), ('athletic', 'Athletic'),
        ('jacked', 'Jacked'), ('average', 'Average'), ('curvy', 'Curvy'), ('a little extra', 'A Little Extra'),
        ('full figured', 'Full Figured'), ('overweight', 'Overweight')
    ])

    class Meta:
        db_table = 'PreferencesBodyType'

class PreferencesEducation(models.Model):
    preferences_education_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    education_level = models.CharField(max_length=20, choices=[
        ('secondary school', 'Secondary School'), ('diploma', 'Diploma'),
        ('undergraduate', 'Undergraduate'), ('postgraduate', 'Postgraduate')
    ])

    class Meta:
        db_table = 'PreferencesEducation'

class PreferencesReligion(models.Model):
    preferences_religion_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    religion_type = models.CharField(max_length=15, choices=[
        ('agnostic', 'Agnostic'), ('atheist', 'Atheist'), ('buddhist', 'Buddhist'), ('catholic', 'Catholic'),
        ('christian', 'Christian'), ('hindu', 'Hindu'), ('islam', 'Islam'), ('jewish', 'Jewish'),
        ('others', 'Others')
    ])

    class Meta:
        db_table = 'PreferencesReligion'

class PreferencesEthnicity(models.Model):
    preferences_ethnicity_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    ethnicity_type = models.CharField(max_length=20, choices=[
        ('asian', 'Asian'), ('black', 'Black'), ('hispanic', 'Hispanic'), ('middle eastern', 'Middle Eastern'),
        ('white', 'White'), ('mixed', 'Mixed'), ('other', 'Other')
    ])

    class Meta:
        db_table = 'PreferencesEthnicity'

class PreferencesPolitics(models.Model):
    preferences_politics_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    politics_type = models.CharField(max_length=20, choices=[
        ('liberal', 'Liberal'), ('moderate', 'Moderate'), ('conservative', 'Conservative'),
        ('not political', 'Not Political'), ('other', 'Other')
    ])

    class Meta:
        db_table = 'PreferencesPolitics'

class PreferencesSmoking(models.Model):
    preferences_smoking_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    smoking_type = models.CharField(max_length=10, choices=[('yes', 'Yes'), ('sometimes', 'Sometimes'), ('no', 'No')])

    class Meta:
        db_table = 'PreferencesSmoking'

class PreferencesDrinking(models.Model):
    preferences_drinking_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    drinking_type = models.CharField(max_length=10, choices=[('yes', 'Yes'), ('sometimes', 'Sometimes'), ('no', 'No')])

    class Meta:
        db_table = 'PreferencesDrinking'

class PreferencesDrug(models.Model):
    preferences_drug_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    drug_type = models.CharField(max_length=10, choices=[('yes', 'Yes'), ('sometimes', 'Sometimes'), ('no', 'No')])

    class Meta:
        db_table = 'PreferencesDrug'

class PreferencesHasKids(models.Model):
    preferences_haskids_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    has_kids_type = models.CharField(max_length=5, choices=[('yes', 'Yes'), ('no', 'No')])

    class Meta:
        db_table = 'PreferencesHasKids'

class PreferencesWantsKids(models.Model):
    preferences_wantskids_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    wants_kids_type = models.CharField(max_length=30, choices=[
        ("don't want kids", "Don't Want Kids"), ('open to kids', 'Open to Kids'), ('want kids', 'Want Kids')
    ])

    class Meta:
        db_table = 'PreferencesWantsKids'

class PreferencesLanguage(models.Model):
    preferences_language_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    language_id_fk = models.OneToOneField(Language, models.DO_NOTHING, db_column='language_id_fk')

    class Meta:
        db_table = 'PreferencesLanguage'

class PreferencesZodiac(models.Model):
    preferences_zodiac_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    zodiac_type = models.CharField(max_length=20, choices=[
        ('aries', 'Aries'), ('taurus', 'Taurus'), ('gemini', 'Gemini'), ('cancer', 'Cancer'), ('leo', 'Leo'),
        ('virgo', 'Virgo'), ('libra', 'Libra'), ('scorpio', 'Scorpio'), ('sagittarius', 'Sagittarius'),
        ('capricorn', 'Capricorn'), ('aquarius', 'Aquarius'), ('pisces', 'Pisces')
    ])

    class Meta:
        db_table = 'PreferencesZodiac'

class PreferencesRelationship(models.Model):
    preferences_relationship_id = models.AutoField(primary_key=True)
    preference_id_fk = models.OneToOneField(Preferences, models.CASCADE, db_column='preference_id_fk')
    relationship_type = models.CharField(max_length=25, choices=[
        ('life partner', 'Life Partner'), ('long-term relationship', 'Long-Term Relationship'),
        ('short-term relationship', 'Short-Term Relationship'), ('casual', 'Casual')
    ])

    class Meta:
        db_table = 'PreferencesRelationship'
