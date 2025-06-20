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

        user = self.model(
            user_id=str(uuid.uuid4()),
            email=email,
            role=extra_fields.get('role', 'user'),
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


