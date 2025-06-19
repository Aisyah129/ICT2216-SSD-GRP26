# authentication/models.py

from django.db import models
from django.utils import timezone

class User(models.Model):
    user_id = models.CharField(max_length=36, primary_key=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128)
    is_premium = models.BooleanField(default=False)
    role = models.CharField(max_length=10, default='user')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'User'
        managed = False  # Because you're using an existing table

    def __str__(self):
        return self.email

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
