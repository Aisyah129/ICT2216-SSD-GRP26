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
