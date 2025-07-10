from django.contrib.auth.backends import BaseBackend
from authentication.models import User
from axes.handlers.proxy import AxesProxyHandler

class CustomBackendForAxes(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 🛡️ Prevent authentication if the request is locked
        if request and AxesProxyHandler.is_locked(request):
            return None  # Axes will not raise; your view will handle the message

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
