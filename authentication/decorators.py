# authentication/decorators.py
from functools import wraps
from django.shortcuts import redirect

def user_only(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'user':
            return view_func(request, *args, **kwargs)
        return redirect('admin_dashboard')  # Block access for admins
    return wrapper
