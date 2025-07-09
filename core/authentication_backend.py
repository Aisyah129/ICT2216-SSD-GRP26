from django.contrib.auth.backends import BaseBackend
from authentication.models import User

class CustomBackendForAxes(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user  # Success for Axes
        except User.DoesNotExist:
            return None  # Failure for Axes
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
