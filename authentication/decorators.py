# authentication/decorators.py
from functools import wraps
from django.shortcuts import redirect
from authentication.utils import has_permission

def user_only(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')  # redirect unauthenticated users
        if request.user.role == 'user':  # Explicit role check
            return view_func(request, *args, **kwargs)
        # Admins or others redirected safely
        return redirect('browse')  # safer than admin_dashboard
    return wrapper
