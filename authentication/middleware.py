
import datetime
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            last_activity = request.session.get('last_activity')

            if last_activity:
                last_activity = datetime.datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                if (datetime.datetime.now() - last_activity).seconds > 900:
                    # Set flag before logout
                    messages.info(request, "timeout")
                    logout(request)
                    return HttpResponseRedirect(reverse('login'))

            request.session['last_activity'] = current_time

        return self.get_response(request)
    
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

class SessionValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip static files and unauthenticated pages like login/register
        public_paths = [
            reverse('login'),
            reverse('register'),
            reverse('verify_email'),
            reverse('password_reset'),
            reverse('verify_reset_code'),
            reverse('set_new_password')
        ]

        if request.path in public_paths or request.path.startswith('/static/'):
            return self.get_response(request)

        if request.user.is_authenticated:
            session_ip = request.session.get('ip')
            session_ua = request.session.get('ua')
            current_ip = get_client_ip(request)
            current_ua = request.META.get('HTTP_USER_AGENT')

            if (session_ip and session_ip != current_ip) or (session_ua and session_ua != current_ua):
                logout(request)
                return redirect('login')  # You can redirect elsewhere if preferred

        return self.get_response(request)
